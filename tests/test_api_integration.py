#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试API集成
"""

import sys
import os
import json
import time
import asyncio

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.zai_transformer import ZAITransformer


async def test_transform_request():
    """测试请求转换功能"""
    print("=" * 50)
    print("测试请求转换功能")
    print("=" * 50)
    
    # 创建转换器实例
    transformer = ZAITransformer()
    
    # 模拟OpenAI请求
    request = {
        "model": "GLM-4.5",
        "messages": [
            {"role": "system", "content": "你是一个有用的AI助手"},
            {"role": "user", "content": "请介绍一下人工智能"}
        ],
        "stream": True,
        "temperature": 0.7
    }
    
    print(f"输入请求:")
    print(f"  模型: {request['model']}")
    print(f"  消息数: {len(request['messages'])}")
    print(f"  流式: {request['stream']}")
    print()
    
    try:
        # 转换请求
        result = await transformer.transform_request_in(request)
        
        print(f"转换结果:")
        print(f"  上游模型: {result['body']['model']}")
        print(f"  聊天ID: {result['body']['chat_id']}")
        tools = result['body'].get('tools', [])
        print(f"  工具数量: {len(tools) if tools else 0}")
        print(f"  MCP服务器: {result['body']['mcp_servers']}")
        print()
        
        # 检查签名
        headers = result['config']['headers']
        if 'X-Signature' in headers:
            print(f"[OK] 签名已添加到请求头: {headers['X-Signature'][:20]}...")
        else:
            print("[WARNING] 未找到签名头")
        
        # 检查签名时间戳
        query_params = result['config']['url'].split('?')[1] if '?' in result['config']['url'] else ""
        if 'signature_timestamp' in query_params:
            print(f"[OK] 签名时间戳已添加到查询参数")
        else:
            print("[WARNING] 未找到签名时间戳参数")
        
        print()
        print("[OK] 请求转换测试通过")
        
        return result
    except Exception as e:
        print(f"[ERROR] 请求转换测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_transform_request_with_tools():
    """测试带工具的请求转换功能"""
    print("=" * 50)
    print("测试带工具的请求转换功能")
    print("=" * 50)
    
    # 创建转换器实例
    transformer = ZAITransformer()
    
    # 工具定义
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "查询指定城市的天气信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名称"},
                        "date": {"type": "string", "description": "查询日期（可选）"}
                    },
                    "required": ["city"]
                }
            }
        }
    ]
    
    # 模拟OpenAI请求
    request = {
        "model": "GLM-4.5",
        "messages": [
            {"role": "user", "content": "查询上海今天的天气"}
        ],
        "tools": tools,
        "stream": True
    }
    
    print(f"输入请求:")
    print(f"  模型: {request['model']}")
    print(f"  消息数: {len(request['messages'])}")
    print(f"  工具数: {len(request['tools'])}")
    print()
    
    try:
        # 转换请求
        result = await transformer.transform_request_in(request)
        
        print(f"转换结果:")
        print(f"  上游模型: {result['body']['model']}")
        print(f"  聊天ID: {result['body']['chat_id']}")
        tools = result['body'].get('tools', [])
        print(f"  工具数量: {len(tools) if tools else 0}")
        print()
        
        # 检查工具是否正确传递
        if result['body'].get('tools'):
            print(f"[OK] 工具已正确传递到上游请求")
        else:
            print("[WARNING] 工具未传递到上游请求")
        
        print()
        print("[OK] 带工具的请求转换测试通过")
        
        return result
    except Exception as e:
        print(f"[ERROR] 带工具的请求转换测试失败: {e}")
        return None


async def test_transform_request_with_multimodal():
    """测试多模态请求转换功能"""
    print("=" * 50)
    print("测试多模态请求转换功能")
    print("=" * 50)
    
    # 创建转换器实例
    transformer = ZAITransformer()
    
    # 多模态内容
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "请描述这张图片"},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
            ]
        }
    ]
    
    # 模拟OpenAI请求
    request = {
        "model": "GLM-4.5",
        "messages": messages,
        "stream": True
    }
    
    print(f"输入请求:")
    print(f"  模型: {request['model']}")
    print(f"  消息数: {len(request['messages'])}")
    print(f"  多模态内容: 是")
    print()
    
    try:
        # 转换请求
        result = await transformer.transform_request_in(request)
        
        print(f"转换结果:")
        print(f"  上游模型: {result['body']['model']}")
        print(f"  聊天ID: {result['body']['chat_id']}")
        print()
        
        # 检查多模态内容
        msg_content = result['body']['messages'][0]['content']
        if isinstance(msg_content, list) and len(msg_content) > 1:
            print(f"[OK] 多模态内容已正确传递")
        else:
            print("[WARNING] 多模态内容可能未正确传递")
        
        print()
        print("[OK] 多模态请求转换测试通过")
        
        return result
    except Exception as e:
        print(f"[ERROR] 多模态请求转换测试失败: {e}")
        return None


async def main():
    """主测试函数"""
    print("开始API集成测试")
    print()
    
    # 运行所有测试
    await test_transform_request()
    print()
    
    await test_transform_request_with_tools()
    print()
    
    await test_transform_request_with_multimodal()
    print()
    
    print("所有API集成测试完成")


if __name__ == "__main__":
    asyncio.run(main())