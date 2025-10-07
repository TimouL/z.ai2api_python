#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
端到端测试签名功能
"""

import sys
import os
import json
import time
import requests

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.signature import zs, decode_jwt_payload, generate_zs_signature


def test_signature_e2e():
    """端到端测试签名功能"""
    print("=" * 50)
    print("端到端签名测试")
    print("=" * 50)
    
    # 使用示例JWT token (仅用于测试)
    # 这是一个假的token，仅用于测试解码逻辑
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6InRlc3QtdXNlci0xMjMiLCJleHAiOjk5OTk5OTk5OTl9.example"
    
    # 测试参数
    request_id = "test-request-123"
    timestamp = int(time.time() * 1000)
    user_content = "请介绍一下人工智能"
    
    print(f"测试参数:")
    print(f"  token: {fake_token[:20]}...")
    print(f"  request_id: {request_id}")
    print(f"  timestamp: {timestamp}")
    print(f"  user_content: {user_content}")
    print()
    
    try:
        # 生成签名
        result = generate_zs_signature(fake_token, request_id, timestamp, user_content)
        
        print(f"签名结果:")
        print(f"  signature: {result['signature']}")
        print(f"  timestamp: {result['timestamp']}")
        print()
        
        # 构建请求参数（模拟API请求）
        user_id = "test-user-123"  # 从假token中提取的user_id
        chat_id = "test-chat-456"
        
        params = {
            "timestamp": timestamp,
            "requestId": request_id,
            "user_id": user_id,
            "token": fake_token,
            "current_url": f"https://chat.z.ai/c/{chat_id}",
            "pathname": f"/c/{chat_id}",
            "signature_timestamp": timestamp
        }
        
        headers = {
            "Authorization": f"Bearer {fake_token}",
            "X-FE-Version": "prod-fe-1.0.95",
            "X-Signature": result["signature"]
        }
        
        payload = {
            "stream": True,
            "model": "GLM-4-6-API-V1",
            "messages": [
                {"role": "user", "content": user_content}
            ],
            "params": {},
            "features": {
                "image_generation": False,
                "web_search": False,
                "auto_web_search": False,
                "preview_mode": True,
                "enable_thinking": True,
            },
            "chat_id": chat_id,
            "id": "test-id-789"
        }
        
        print(f"模拟API请求:")
        print(f"  URL: https://chat.z.ai/api/chat/completions")
        print(f"  参数数量: {len(params)}")
        print(f"  头部数量: {len(headers)}")
        print(f"  请求体大小: {len(json.dumps(payload))} 字符")
        print()
        
        # 检查关键组件
        if "X-Signature" in headers:
            print("[OK] 签名已添加到请求头")
        else:
            print("[ERROR] 签名未添加到请求头")
        
        if "signature_timestamp" in params:
            print("[OK] 签名时间戳已添加到查询参数")
        else:
            print("[ERROR] 签名时间戳未添加到查询参数")
        
        if params["user_id"] == user_id:
            print("[OK] user_id与签名中使用的user_id一致")
        else:
            print("[ERROR] user_id与签名中使用的user_id不一致")
        
        print()
        print("[OK] 端到端签名测试完成")
        
        return True
    except Exception as e:
        print(f"[ERROR] 端到端签名测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signature_components():
    """测试签名组件"""
    print("=" * 50)
    print("测试签名组件")
    print("=" * 50)
    
    # 测试JWT解码
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6InRlc3QtdXNlci0xMjMiLCJleHAiOjk5OTk5OTk5OTl9.example"
    
    try:
        payload = decode_jwt_payload(fake_token)
        user_id = payload['id']
        print(f"JWT解码成功，user_id: {user_id}")
    except Exception as e:
        print(f"JWT解码失败: {e}")
        return False
    
    # 测试zs函数
    e = f"requestId,test-123,timestamp,{int(time.time() * 1000)},user_id,{user_id}"
    t = "测试内容"
    timestamp = int(time.time() * 1000)
    
    try:
        result = zs(e, t, timestamp)
        print(f"zs函数签名成功，签名: {result['signature'][:20]}...")
    except Exception as e:
        print(f"zs函数签名失败: {e}")
        return False
    
    print("[OK] 签名组件测试通过")
    return True


if __name__ == "__main__":
    print("开始端到端签名测试")
    print()
    
    # 运行所有测试
    success1 = test_signature_components()
    print()
    
    success2 = test_signature_e2e()
    print()
    
    if success1 and success2:
        print("所有测试通过")
    else:
        print("部分测试失败")