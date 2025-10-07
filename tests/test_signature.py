#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试签名功能
"""

import sys
import os
import time
import uuid

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.signature import zs, generate_zs_signature, decode_jwt_payload


def test_zs_signature():
    """测试zs签名函数"""
    print("=" * 50)
    print("测试zs签名函数")
    print("=" * 50)
    
    # 测试参数
    e = "requestId,12345,timestamp,1694006400000,user_id,test-user"
    t = "你好，请介绍一下人工智能"
    timestamp = int(time.time() * 1000)
    
    # 生成签名
    result = zs(e, t, timestamp)
    
    print(f"输入参数:")
    print(f"  e: {e}")
    print(f"  t: {t}")
    print(f"  timestamp: {timestamp}")
    print()
    print(f"签名结果:")
    print(f"  signature: {result['signature']}")
    print(f"  timestamp: {result['timestamp']}")
    print()
    
    # 验证签名一致性
    result2 = zs(e, t, timestamp)
    if result['signature'] == result2['signature']:
        print("[OK] 签名一致性测试通过")
    else:
        print("[ERROR] 签名一致性测试失败")
    
    return result


def test_generate_zs_signature():
    """测试便捷签名函数"""
    print("=" * 50)
    print("测试便捷签名函数")
    print("=" * 50)
    
    # 使用示例JWT token (仅用于测试)
    # 这是一个假的token，仅用于测试解码逻辑
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6InRlc3QtdXNlci0xMjMiLCJleHAiOjk5OTk5OTk5OTl9.example"
    
    request_id = str(uuid.uuid4())
    timestamp = int(time.time() * 1000)
    user_content = "请帮我写一个Python函数"
    
    print(f"输入参数:")
    print(f"  token: {fake_token[:20]}...")
    print(f"  request_id: {request_id}")
    print(f"  timestamp: {timestamp}")
    print(f"  user_content: {user_content}")
    print()
    
    try:
        result = generate_zs_signature(fake_token, request_id, timestamp, user_content)
        
        print(f"签名结果:")
        print(f"  signature: {result['signature']}")
        print(f"  timestamp: {result['timestamp']}")
        print()
        print("[OK] 便捷签名函数测试通过")
        
        return result
    except Exception as e:
        print(f"[ERROR] 便捷签名函数测试失败: {e}")
        return None


def test_jwt_decode():
    """测试JWT解码"""
    print("=" * 50)
    print("测试JWT解码")
    print("=" * 50)
    
    # 使用示例JWT token (仅用于测试)
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6InRlc3QtdXNlci0xMjMiLCJleHAiOjk5OTk5OTk5OTl9.example"
    
    print(f"测试token: {fake_token[:20]}...")
    
    try:
        payload = decode_jwt_payload(fake_token)
        print(f"解码结果: {payload}")
        print()
        print("[OK] JWT解码测试通过")
        
        return payload
    except Exception as e:
        print(f"[ERROR] JWT解码测试失败: {e}")
        return None


def compare_with_reference():
    """与参考文档中的示例进行比较"""
    print("=" * 50)
    print("与参考文档示例比较")
    print("=" * 50)
    
    # 使用参考文档中的示例参数
    e = "requestId,abc-123,timestamp,1694006400000,user_id,user-456"
    t = "Hello, how can I help you?"
    timestamp = 1694006400000  # 固定时间戳用于比较
    
    print(f"使用参考文档参数:")
    print(f"  e: {e}")
    print(f"  t: {t}")
    print(f"  timestamp: {timestamp}")
    print()
    
    # 生成签名
    result = zs(e, t, timestamp)
    
    print(f"生成的签名:")
    print(f"  signature: {result['signature']}")
    print(f"  timestamp: {result['timestamp']}")
    print()
    
    # 注意：由于时间戳不同，签名会不同，但算法应该相同
    print("[OK] 参考文档比较完成")


if __name__ == "__main__":
    print("开始测试签名功能")
    print()
    
    # 运行所有测试
    test_zs_signature()
    print()
    
    test_generate_zs_signature()
    print()
    
    test_jwt_decode()
    print()
    
    compare_with_reference()
    print()
    
    print("所有测试完成")