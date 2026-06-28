#!/usr/bin/env python3
"""
测试 noVNC WebSocket 连接
"""

import asyncio
import websockets

async def test_vnc_connection():
    uri = "ws://localhost:6080/websockify"
    print(f"正在连接到: {uri}")

    try:
        async with websockets.connect(uri, timeout=5) as websocket:
            print("✅ WebSocket 连接成功！")

            # 尝试接收一些数据
            try:
                data = await asyncio.wait_for(websocket.recv(), timeout=2)
                print(f"✅ 接收到数据: {len(data)} 字节")
                print(f"   数据类型: {type(data)}")
                if isinstance(data, bytes):
                    print(f"   前20字节: {data[:20]}")
            except asyncio.TimeoutError:
                print("⚠️  2秒内未接收到数据（这是正常的，VNC需要握手）")

            print("\n✅ noVNC WebSocket 服务正常运行！")
            return True

    except ConnectionRefusedError:
        print("❌ 连接被拒绝 - 服务未运行")
        return False
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ 无效的状态码: {e}")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_vnc_connection())
    exit(0 if result else 1)
