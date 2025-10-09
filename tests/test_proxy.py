#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试代理配置
"""

import os
import asyncio
import httpx


async def test_proxy():
    """测试代理连接"""
    print("=== 代理配置测试 ===\n")
    
    # 读取环境变量
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    
    print(f"HTTP_PROXY: {http_proxy or '未配置'}")
    print(f"HTTPS_PROXY: {https_proxy or '未配置'}\n")
    
    # 配置代理
    # httpx 使用 proxy 参数（单数形式），优先使用 HTTPS 代理
    proxy = None
    if https_proxy:
        proxy = https_proxy
        print(f"✅ 使用 HTTPS 代理: {proxy}\n")
    elif http_proxy:
        proxy = http_proxy
        print(f"✅ 使用 HTTP 代理: {proxy}\n")
    else:
        print("⚠️  未配置代理，将使用直连\n")
    
    # 测试连接
    test_urls = [
        "https://chat.z.ai",
        "https://www.google.com",
    ]
    
    async with httpx.AsyncClient(proxy=proxy, timeout=10.0) as client:
        for url in test_urls:
            try:
                print(f"正在测试连接: {url}...")
                response = await client.get(url)
                print(f"✅ 连接成功: {url} (状态码: {response.status_code})")
            except Exception as e:
                print(f"❌ 连接失败: {url}")
                print(f"   错误: {e}")
            print()


if __name__ == "__main__":
    # 从 .env 文件加载环境变量
    try:
        from dotenv import load_dotenv
        if load_dotenv():
            print("✅ .env 文件加载成功\n")
        else:
            print("⚠️  未找到 .env 文件\n")
    except ImportError:
        print("⚠️  未安装 python-dotenv，跳过 .env 加载\n")
    
    # 运行测试
    asyncio.run(test_proxy())

