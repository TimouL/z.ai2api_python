"""
OpenAI API endpoints
"""

import time
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from app.core.config import settings
from app.models.schemas import OpenAIRequest, Message, ModelsResponse, Model
from app.utils.helpers import debug_log
from app.core.zai_transformer import ZAITransformer, generate_uuid
from app.utils.sse_tool_handler import SSEToolHandler

router = APIRouter()

# 全局转换器实例
transformer = ZAITransformer()


@router.get("/v1/models")
async def list_models():
    """List available models"""
    current_time = int(time.time())
    response = ModelsResponse(
        data=[
            Model(id=settings.PRIMARY_MODEL, created=current_time, owned_by="z.ai"),
            Model(id=settings.THINKING_MODEL, created=current_time, owned_by="z.ai"),
            Model(id=settings.SEARCH_MODEL, created=current_time, owned_by="z.ai"),
            Model(id=settings.AIR_MODEL, created=current_time, owned_by="z.ai"),
        ]
    )
    return response


@router.post("/v1/chat/completions")
async def chat_completions(request: OpenAIRequest, authorization: str = Header(...)):
    """Handle chat completion requests with ZAI transformer"""
    role = request.messages[0].role if request.messages else "unknown"
    debug_log(f"😶‍🌫️ 收到 客户端 请求 - 模型: {request.model}, 流式: {request.stream}, 消息数: {len(request.messages)}, 角色: {role}, 工具数: {len(request.tools) if request.tools else 0}")
    
    try:
        # Validate API key (skip if SKIP_AUTH_TOKEN is enabled)
        if not settings.SKIP_AUTH_TOKEN:
            if not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
            
            api_key = authorization[7:]
            if api_key != settings.AUTH_TOKEN:
                raise HTTPException(status_code=401, detail="Invalid API key")
            
        # 使用新的转换器转换请求
        request_dict = request.model_dump()
        debug_log("🔄 开始转换请求格式: OpenAI -> Z.AI")
        
        transformed = await transformer.transform_request_in(request_dict)

        # 调用上游API
        async def stream_response():
            """流式响应生成器（包含重试机制）"""
            retry_count = 0
            last_error = None
            current_token = transformed.get("token", "")  # 获取当前使用的token

            while retry_count <= settings.MAX_RETRIES:
                try:
                    # 如果是重试，重新获取令牌并更新请求
                    if retry_count > 0:
                        delay = 2.0
                        debug_log(f"重试请求 ({retry_count}/{settings.MAX_RETRIES}) - 等待 {delay:.1f}s")
                        await asyncio.sleep(delay)

                        # 标记前一个token失败
                        if current_token:
                            transformer.mark_token_failure(current_token, Exception(f"Retry {retry_count}: {last_error}"))

                        # 重新获取令牌
                        debug_log("🔑 重新获取令牌用于重试...")
                        new_token = await transformer.get_token()
                        if not new_token:
                            debug_log("❌ 重试时无法获取有效的认证令牌")
                            raise Exception("重试时无法获取有效的认证令牌")
                        transformed["config"]["headers"]["Authorization"] = f"Bearer {new_token}"
                        current_token = new_token

                    async with httpx.AsyncClient(timeout=60.0) as client:
                        # 发送请求到上游
                        debug_log(f"🎯 发送请求到 Z.AI: {transformed['config']['url']}")
                        async with client.stream(
                            "POST",
                            transformed["config"]["url"],
                            json=transformed["body"],
                            headers=transformed["config"]["headers"],
                        ) as response:
                            # 检查响应状态码
                            if response.status_code == 400:
                                # 400 错误，触发重试
                                error_text = await response.aread()
                                error_msg = error_text.decode('utf-8', errors='ignore')
                                debug_log(f"❌ 上游返回 400 错误 (尝试 {retry_count + 1}/{settings.MAX_RETRIES + 1})")
                                debug_log(f"上游错误响应: {error_msg}")

                                retry_count += 1
                                last_error = f"400 Bad Request: {error_msg}"

                                # 如果还有重试机会，继续循环
                                if retry_count <= settings.MAX_RETRIES:
                                    continue
                                else:
                                    # 达到最大重试次数，抛出错误
                                    debug_log(f"❌ 达到最大重试次数 ({settings.MAX_RETRIES})，请求失败")
                                    error_response = {
                                        "error": {
                                            "message": f"Request failed after {settings.MAX_RETRIES} retries: {last_error}",
                                            "type": "upstream_error",
                                            "code": 400
                                        }
                                    }
                                    yield f"data: {json.dumps(error_response)}\n\n"
                                    yield "data: [DONE]\n\n"
                                    return

                            elif response.status_code != 200:
                                # 其他错误，直接返回
                                debug_log(f"❌ 上游返回错误: {response.status_code}")
                                error_text = await response.aread()
                                error_msg = error_text.decode('utf-8', errors='ignore')
                                debug_log(f"❌ 错误详情: {error_msg}")

                                error_response = {
                                    "error": {
                                        "message": f"Upstream error: {response.status_code}",
                                        "type": "upstream_error",
                                        "code": response.status_code
                                    }
                                }
                                yield f"data: {json.dumps(error_response)}\n\n"
                                yield "data: [DONE]\n\n"
                                return

                            # 200 成功，处理响应
                            debug_log(f"✅ Z.AI 响应成功，开始处理 SSE 流")
                            if retry_count > 0:
                                debug_log(f"✨ 第 {retry_count} 次重试成功")

                            # 标记token使用成功
                            if current_token:
                                transformer.mark_token_success(current_token)

                            # 初始化工具处理器（如果需要）
                            has_tools = transformed["body"].get("tools") is not None
                            has_mcp_servers = bool(transformed["body"].get("mcp_servers"))
                            tool_handler = None

                            # 如果有工具定义或MCP服务器，都需要工具处理器
                            if has_tools or has_mcp_servers:
                                chat_id = transformed["body"]["chat_id"]
                                model = request.model
                                tool_handler = SSEToolHandler(chat_id, model)

                                if has_tools and has_mcp_servers:
                                    debug_log(f"🔧 初始化工具处理器: {len(transformed['body'].get('tools', []))} 个OpenAI工具 + {len(transformed['body'].get('mcp_servers', []))} 个MCP服务器")
                                elif has_tools:
                                    debug_log(f"🔧 初始化工具处理器: {len(transformed['body'].get('tools', []))} 个OpenAI工具")
                                elif has_mcp_servers:
                                    debug_log(f"🔧 初始化工具处理器: {len(transformed['body'].get('mcp_servers', []))} 个MCP服务器")

                            # 处理状态
                            has_thinking = False
                            thinking_signature = None

                            # 处理SSE流
                            buffer = ""
                            line_count = 0
                            debug_log("📡 开始接收 SSE 流数据...")

                            async for line in response.aiter_lines():
                                line_count += 1
                                if not line:
                                    continue

                                # 累积到buffer处理完整的数据行
                                buffer += line + "\n"

                                # 检查是否有完整的data行
                                while "\n" in buffer:
                                    current_line, buffer = buffer.split("\n", 1)
                                    if not current_line.strip():
                                        continue

                                    if current_line.startswith("data:"):
                                        chunk_str = current_line[5:].strip()
                                        if not chunk_str or chunk_str == "[DONE]":
                                            if chunk_str == "[DONE]":
                                                yield "data: [DONE]\n\n"
                                            continue

                                        debug_log(f"📦 解析数据块: {chunk_str[:200]}..." if len(chunk_str) > 200 else f"📦 解析数据块: {chunk_str}")

                                        try:
                                            chunk = json.loads(chunk_str)

                                            if chunk.get("type") == "chat:completion":
                                                data = chunk.get("data", {})
                                                phase = data.get("phase")

                                                # 记录每个阶段（只在阶段变化时记录）
                                                if phase and phase != getattr(stream_response, '_last_phase', None):
                                                    debug_log(f"📈 SSE 阶段: {phase}")
                                                    stream_response._last_phase = phase

                                                # 处理工具调用
                                                if phase == "tool_call" and tool_handler:
                                                    for output in tool_handler.process_tool_call_phase(data, True):
                                                        yield output

                                                # 处理其他阶段（工具结束）
                                                elif phase == "other" and tool_handler:
                                                    for output in tool_handler.process_other_phase(data, True):
                                                        yield output

                                                # 处理思考内容
                                                elif phase == "thinking":
                                                    if not has_thinking:
                                                        has_thinking = True
                                                        # 发送初始角色
                                                        role_chunk = {
                                                            "choices": [
                                                                {
                                                                    "delta": {"role": "assistant"},
                                                                    "finish_reason": None,
                                                                    "index": 0,
                                                                    "logprobs": None,
                                                                }
                                                            ],
                                                            "created": int(time.time()),
                                                            "id": transformed["body"]["chat_id"],
                                                            "model": request.model,
                                                            "object": "chat.completion.chunk",
                                                            "system_fingerprint": "fp_zai_001",
                                                        }
                                                        yield f"data: {json.dumps(role_chunk)}\n\n"

                                                    delta_content = data.get("delta_content", "")
                                                    if delta_content:
                                                        # 处理思考内容格式
                                                        if delta_content.startswith("<details"):
                                                            content = (
                                                                delta_content.split("</summary>\n>")[-1].strip()
                                                                if "</summary>\n>" in delta_content
                                                                else delta_content
                                                            )
                                                        else:
                                                            content = delta_content

                                                        thinking_chunk = {
                                                            "choices": [
                                                                {
                                                                    "delta": {
                                                                        "role": "assistant",
                                                                        "thinking": {"content": content},
                                                                    },
                                                                    "finish_reason": None,
                                                                    "index": 0,
                                                                    "logprobs": None,
                                                                }
                                                            ],
                                                            "created": int(time.time()),
                                                            "id": transformed["body"]["chat_id"],
                                                            "model": request.model,
                                                            "object": "chat.completion.chunk",
                                                            "system_fingerprint": "fp_zai_001",
                                                        }
                                                        yield f"data: {json.dumps(thinking_chunk)}\n\n"

                                                # 处理答案内容
                                                elif phase == "answer":
                                                    edit_content = data.get("edit_content", "")
                                                    delta_content = data.get("delta_content", "")

                                                    # 处理思考结束和答案开始
                                                    if edit_content and "</details>\n" in edit_content:
                                                        if has_thinking:
                                                            # 发送思考签名
                                                            thinking_signature = str(int(time.time() * 1000))
                                                            sig_chunk = {
                                                                "choices": [
                                                                    {
                                                                        "delta": {
                                                                            "role": "assistant",
                                                                            "thinking": {
                                                                                "content": "",
                                                                                "signature": thinking_signature,
                                                                            },
                                                                        },
                                                                        "finish_reason": None,
                                                                        "index": 0,
                                                                        "logprobs": None,
                                                                    }
                                                                ],
                                                                "created": int(time.time()),
                                                                "id": transformed["body"]["chat_id"],
                                                                "model": request.model,
                                                                "object": "chat.completion.chunk",
                                                                "system_fingerprint": "fp_zai_001",
                                                            }
                                                            yield f"data: {json.dumps(sig_chunk)}\n\n"

                                                        # 提取答案内容
                                                        content_after = edit_content.split("</details>\n")[-1]
                                                        if content_after:
                                                            content_chunk = {
                                                                "choices": [
                                                                    {
                                                                        "delta": {
                                                                            "role": "assistant",
                                                                            "content": content_after,
                                                                        },
                                                                        "finish_reason": None,
                                                                        "index": 0,
                                                                        "logprobs": None,
                                                                    }
                                                                ],
                                                                "created": int(time.time()),
                                                                "id": transformed["body"]["chat_id"],
                                                                "model": request.model,
                                                                "object": "chat.completion.chunk",
                                                                "system_fingerprint": "fp_zai_001",
                                                            }
                                                            yield f"data: {json.dumps(content_chunk)}\n\n"

                                                    # 处理增量内容
                                                    elif delta_content:
                                                        # 如果还没有发送角色
                                                        if not has_thinking:
                                                            role_chunk = {
                                                                "choices": [
                                                                    {
                                                                        "delta": {"role": "assistant"},
                                                                        "finish_reason": None,
                                                                        "index": 0,
                                                                        "logprobs": None,
                                                                    }
                                                                ],
                                                                "created": int(time.time()),
                                                                "id": transformed["body"]["chat_id"],
                                                                "model": request.model,
                                                                "object": "chat.completion.chunk",
                                                                "system_fingerprint": "fp_zai_001",
                                                            }
                                                            yield f"data: {json.dumps(role_chunk)}\n\n"

                                                        content_chunk = {
                                                            "choices": [
                                                                {
                                                                    "delta": {
                                                                        "role": "assistant",
                                                                        "content": delta_content,
                                                                    },
                                                                    "finish_reason": None,
                                                                    "index": 0,
                                                                    "logprobs": None,
                                                                }
                                                            ],
                                                            "created": int(time.time()),
                                                            "id": transformed["body"]["chat_id"],
                                                            "model": request.model,
                                                            "object": "chat.completion.chunk",
                                                            "system_fingerprint": "fp_zai_001",
                                                        }
                                                        output_data = f"data: {json.dumps(content_chunk)}\n\n"
                                                        debug_log(f"➡️ 输出内容块到客户端: {output_data[:200]}...")
                                                        yield output_data

                                                    # 处理完成
                                                    if data.get("usage"):
                                                        debug_log(f"📦 完成响应 - 使用统计: {json.dumps(data['usage'])}")

                                                        # 只有在非工具调用模式下才发送普通完成信号
                                                        if not tool_handler or not tool_handler.has_tool_call:
                                                            finish_chunk = {
                                                                "choices": [
                                                                    {
                                                                        "delta": {"role": "assistant", "content": ""},
                                                                        "finish_reason": "stop",
                                                                        "index": 0,
                                                                        "logprobs": None,
                                                                    }
                                                                ],
                                                                "usage": data["usage"],
                                                                "created": int(time.time()),
                                                                "id": transformed["body"]["chat_id"],
                                                                "model": request.model,
                                                                "object": "chat.completion.chunk",
                                                                "system_fingerprint": "fp_zai_001",
                                                            }
                                                            finish_output = f"data: {json.dumps(finish_chunk)}\n\n"
                                                            debug_log(f"➡️ 发送完成信号: {finish_output[:200]}...")
                                                            yield finish_output
                                                            debug_log("➡️ 发送 [DONE]")
                                                            yield "data: [DONE]\n\n"

                                        except json.JSONDecodeError as e:
                                            debug_log(f"❌ JSON解析错误: {e}, 内容: {chunk_str[:200]}")
                                        except Exception as e:
                                            debug_log(f"❌ 处理chunk错误: {e}")

                            # 确保发送结束信号
                            if not tool_handler or not tool_handler.has_tool_call:
                                debug_log("📤 发送最终 [DONE] 信号")
                                yield "data: [DONE]\n\n"

                            debug_log(f"✅ SSE 流处理完成，共处理 {line_count} 行数据")
                            # 成功处理完成，退出重试循环
                            return

                except Exception as e:
                    debug_log(f"❌ 流处理错误: {e}")
                    import traceback
                    debug_log(traceback.format_exc())

                    # 标记token失败
                    if current_token:
                        transformer.mark_token_failure(current_token, e)

                    # 检查是否还可以重试
                    retry_count += 1
                    last_error = str(e)

                    if retry_count > settings.MAX_RETRIES:
                        # 达到最大重试次数，返回错误
                        debug_log(f"❌ 达到最大重试次数 ({settings.MAX_RETRIES})，流处理失败")
                        error_response = {
                            "error": {
                                "message": f"Stream processing failed after {settings.MAX_RETRIES} retries: {last_error}",
                                "type": "stream_error"
                            }
                        }
                        yield f"data: {json.dumps(error_response)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

        # 返回流式响应
        debug_log("🚀 启动 SSE 流式响应")
        
        # 创建一个包装的生成器来追踪数据流
        async def logged_stream():
            chunk_count = 0
            try:
                debug_log("📤 开始向客户端流式传输数据...")
                async for chunk in stream_response():
                    chunk_count += 1
                    debug_log(f"📤 发送块[{chunk_count}]: {chunk[:200]}..." if len(chunk) > 200 else f"  📤 发送块[{chunk_count}]: {chunk}")
                    yield chunk
                debug_log(f"✅ 流式传输完成，共发送 {chunk_count} 个数据块")
            except Exception as e:
                debug_log(f"❌ 流式传输中断: {e}")
                raise
        
        return StreamingResponse(
            logged_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        debug_log(f"❌ 处理请求时发生错误: {str(e)}")
        import traceback

        debug_log(f"❌ 错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")