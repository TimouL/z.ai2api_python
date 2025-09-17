#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
import uuid
import random
from datetime import datetime
from typing import Dict, List, Any, Optional, Generator, AsyncGenerator
import httpx
import asyncio
from fake_useragent import UserAgent

from app.core.config import settings
from app.utils.helpers import debug_log
from app.core.token_manager import token_manager

# 全局 UserAgent 实例（单例模式）
_user_agent_instance = None


def get_user_agent_instance() -> UserAgent:
    """获取或创建 UserAgent 实例（单例模式）"""
    global _user_agent_instance
    if _user_agent_instance is None:
        _user_agent_instance = UserAgent()
    return _user_agent_instance


def get_dynamic_headers(chat_id: str = "") -> Dict[str, str]:
    """生成动态浏览器headers，包含随机User-Agent"""
    ua = get_user_agent_instance()

    # 随机选择浏览器类型，偏向Chrome和Edge
    browser_choices = ["chrome", "chrome", "chrome", "edge", "edge", "firefox", "safari"]
    browser_type = random.choice(browser_choices)

    try:
        if browser_type == "chrome":
            user_agent = ua.chrome
        elif browser_type == "edge":
            user_agent = ua.edge
        elif browser_type == "firefox":
            user_agent = ua.firefox
        elif browser_type == "safari":
            user_agent = ua.safari
        else:
            user_agent = ua.random
    except:
        user_agent = ua.random

    # 提取版本信息
    chrome_version = "139"
    edge_version = "139"

    if "Chrome/" in user_agent:
        try:
            chrome_version = user_agent.split("Chrome/")[1].split(".")[0]
        except:
            pass

    if "Edg/" in user_agent:
        try:
            edge_version = user_agent.split("Edg/")[1].split(".")[0]
            sec_ch_ua = f'"Microsoft Edge";v="{edge_version}", "Chromium";v="{chrome_version}", "Not_A Brand";v="24"'
        except:
            sec_ch_ua = f'"Not_A Brand";v="8", "Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}"'
    elif "Firefox/" in user_agent:
        sec_ch_ua = None  # Firefox不使用sec-ch-ua
    else:
        sec_ch_ua = f'"Not_A Brand";v="8", "Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}"'

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": user_agent,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "X-FE-Version": "prod-fe-1.0.79",
        "Origin": "https://chat.z.ai",
    }

    if sec_ch_ua:
        headers["sec-ch-ua"] = sec_ch_ua
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'

    if chat_id:
        headers["Referer"] = f"https://chat.z.ai/c/{chat_id}"
    else:
        headers["Referer"] = "https://chat.z.ai/"

    return headers


def generate_uuid() -> str:
    """生成UUID v4"""
    return str(uuid.uuid4())


def get_auth_token_sync() -> str:
    """同步获取认证令牌（用于非异步场景）"""
    if settings.ANONYMOUS_MODE:
        try:
            headers = get_dynamic_headers()
            with httpx.Client() as client:
                response = client.get("https://chat.z.ai/api/v1/auths/", headers=headers, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("token", "")
                    if token:
                        debug_log(f"获取访客令牌成功: {token[:20]}...")
                        return token
        except Exception as e:
            debug_log(f"获取访客令牌失败: {e}")

    # 使用token管理器获取备份令牌
    token = token_manager.get_next_token()
    if token:
        debug_log(f"从token池获取令牌: {token[:20]}...")
        return token

    # 没有可用的token
    debug_log("⚠️ 没有可用的备份token")
    return ""


class ZAITransformer:
    """ZAI转换器类"""

    def __init__(self):
        """初始化转换器"""
        self.name = "zai"
        self.base_url = "https://chat.z.ai"
        self.api_url = settings.API_ENDPOINT
        self.auth_url = f"{self.base_url}/api/v1/auths/"

        # 模型映射
        self.model_mapping = {
            settings.PRIMARY_MODEL: "0727-360B-API",  # GLM-4.5
            settings.THINKING_MODEL: "0727-360B-API",  # GLM-4.5-Thinking
            settings.SEARCH_MODEL: "0727-360B-API",  # GLM-4.5-Search
            settings.AIR_MODEL: "0727-106B-API",  # GLM-4.5-Air
        }

    async def get_token(self) -> str:
        """异步获取认证令牌"""
        if settings.ANONYMOUS_MODE:
            try:
                headers = get_dynamic_headers()
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.auth_url, headers=headers, timeout=10.0)
                    if response.status_code == 200:
                        data = response.json()
                        token = data.get("token", "")
                        if token:
                            debug_log(f"获取访客令牌成功: {token[:20]}...")
                            return token
            except Exception as e:
                debug_log(f"异步获取访客令牌失败: {e}")

        # 使用token管理器获取备份令牌
        token = token_manager.get_next_token()
        if token:
            debug_log(f"从token池获取令牌: {token[:20]}...")
            return token

        # 没有可用的token
        debug_log("⚠️ 没有可用的备份token")
        return ""

    def mark_token_success(self, token: str):
        """标记token使用成功"""
        token_manager.mark_token_success(token)

    def mark_token_failure(self, token: str, error: Exception = None):
        """标记token使用失败"""
        token_manager.mark_token_failed(token)

    async def transform_request_in(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换OpenAI请求为z.ai格式
        整合现有功能：模型映射、MCP服务器等
        """
        debug_log(f"🔄 开始转换 OpenAI 请求到 Z.AI 格式: {request.get('model', settings.PRIMARY_MODEL)} -> Z.AI")

        # 获取认证令牌
        token = await self.get_token()
        debug_log(f"  使用令牌: {token[:20] if token else 'None'}...")

        # 检查token是否有效
        if not token:
            debug_log("❌ 无法获取有效的认证令牌")
            raise Exception("无法获取有效的认证令牌，请检查匿名模式配置或token池配置")

        # 确定请求的模型特性
        requested_model = request.get("model", settings.PRIMARY_MODEL)
        is_thinking = requested_model == settings.THINKING_MODEL or request.get("reasoning", False)
        is_search = requested_model == settings.SEARCH_MODEL
        is_air = requested_model == settings.AIR_MODEL

        # 获取上游模型ID（使用模型映射）
        upstream_model_id = self.model_mapping.get(requested_model, "0727-360B-API")
        debug_log(f"  模型映射: {requested_model} -> {upstream_model_id}")
        debug_log(f"  模型特性检测: is_search={is_search}, is_thinking={is_thinking}, is_air={is_air}")

        # 处理消息列表
        debug_log(f"  开始处理 {len(request.get('messages', []))} 条消息")
        messages = []
        for idx, orig_msg in enumerate(request.get("messages", [])):
            msg = orig_msg.copy()

            # 处理system角色转换
            if msg.get("role") == "system":
                msg["role"] = "user"
                content = msg.get("content")

                if isinstance(content, list):
                    msg["content"] = [
                        {"type": "text", "text": "This is a system command, you must enforce compliance."}
                    ] + content
                elif isinstance(content, str):
                    msg["content"] = f"This is a system command, you must enforce compliance.{content}"

            # 处理user角色的图片内容
            elif msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    new_content = []
                    for part_idx, part in enumerate(content):
                        # 处理图片URL（支持base64和http URL）
                        if (
                            part.get("type") == "image_url"
                            and part.get("image_url", {}).get("url")
                            and isinstance(part["image_url"]["url"], str)
                        ):
                            debug_log(f"    消息[{idx}]内容[{part_idx}]: 检测到图片URL")
                            # 直接传递图片内容
                            new_content.append(part)
                        else:
                            new_content.append(part)
                    msg["content"] = new_content

            # 处理assistant消息中的reasoning_content
            elif msg.get("role") == "assistant" and msg.get("reasoning_content"):
                # 如果有reasoning_content，保留它
                pass

            messages.append(msg)

        # 构建MCP服务器列表
        mcp_servers = []
        if is_search:
            mcp_servers.append("deep-web-search")
            debug_log(f"🔍 检测到搜索模型，添加 deep-web-search MCP 服务器")

        debug_log(f"  MCP服务器列表: {mcp_servers}")
            
        # 构建上游请求体
        chat_id = generate_uuid()

        body = {
            "stream": True,  # 总是使用流式
            "model": upstream_model_id,  # 使用映射后的模型ID
            "messages": messages,
            "params": {},
            "features": {
                "image_generation": False,
                "web_search": is_search,
                "auto_web_search": is_search,
                "preview_mode": False,
                "flags": [],
                "features": [],
                "enable_thinking": is_thinking,
            },
            "background_tasks": {
                "title_generation": False,
                "tags_generation": False,
            },
            "mcp_servers": mcp_servers,  # 保留MCP服务器支持
            "variables": {
                "{{USER_NAME}}": "Guest",
                "{{USER_LOCATION}}": "Unknown",
                "{{CURRENT_DATETIME}}": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "{{CURRENT_DATE}}": datetime.now().strftime("%Y-%m-%d"),
                "{{CURRENT_TIME}}": datetime.now().strftime("%H:%M:%S"),
                "{{CURRENT_WEEKDAY}}": datetime.now().strftime("%A"),
                "{{CURRENT_TIMEZONE}}": "Asia/Shanghai",  # 使用更合适的时区
                "{{USER_LANGUAGE}}": "zh-CN",
            },
            "model_item": {
                "id": upstream_model_id,
                "name": requested_model,
                "owned_by": "z.ai"
            },
            "chat_id": chat_id,
            "id": generate_uuid(),
        }

        # 处理工具支持
        if settings.TOOL_SUPPORT and not is_thinking and request.get("tools"):
            body["tools"] = request["tools"]
            debug_log(f"启用工具支持: {len(request['tools'])} 个工具")
        else:
            body["tools"] = None

        # 构建请求配置
        dynamic_headers = get_dynamic_headers(chat_id)

        config = {
            "url": self.api_url,  # 使用原始URL
            "headers": {
                **dynamic_headers,  # 使用动态生成的headers
                "Authorization": f"Bearer {token}",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            },
        }

        debug_log("✅ 请求转换完成")

        # 记录关键的请求信息用于调试
        debug_log(f"  📋 发送到Z.AI的关键信息:")
        debug_log(f"    - 上游模型: {body['model']}")
        debug_log(f"    - MCP服务器: {body['mcp_servers']}")
        debug_log(f"    - web_search: {body['features']['web_search']}")
        debug_log(f"    - auto_web_search: {body['features']['auto_web_search']}")
        debug_log(f"    - 消息数量: {len(body['messages'])}")
        tools_count = len(body.get('tools') or [])
        debug_log(f"    - 工具数量: {tools_count}")

        # 返回转换后的请求数据
        return {
            "body": body,
            "config": config,
            "token": token
        }
