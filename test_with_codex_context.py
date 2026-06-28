#!/usr/bin/env python3
"""
测试带 Codex 上下文的 AMD 股价搜索
模拟真实场景：包含历史对话、系统消息等
"""

import json
import httpx

VLLM_URL = "http://localhost:8102/v1/chat/completions"
MODEL = "/home/xilinx/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-W4A16-llmcompressor"

# 工具定义
tools = [
    {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "查询指定地点的天气信息。用户问天气、会不会下雨时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、深圳"
                    }
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索网络信息。用于查询实时信息，包括：新闻、赛程、股价、汇率、产品价格、公司信息等。用户说'搜索'、'查询'、'找一下'时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如：'AMD股价'、'NBA赛程'、'ChatGPT是什么'"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def test_with_history():
    """测试带历史对话的情况"""
    print("=" * 80)
    print("测试场景 1: 带历史对话（模拟实际使用）")
    print("=" * 80)

    # 模拟之前的对话历史
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！我是你的语音助手，有什么可以帮助你的吗？"},
        {"role": "user", "content": "搜索一下AMD的股价"}  # 当前问题
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 2000
    }

    print(f"\nMessages: {len(messages)} 条消息")
    for i, m in enumerate(messages):
        print(f"  {i+1}. {m['role']}: {m['content'][:50]}...")

    try:
        response = httpx.post(VLLM_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            message = data["choices"][0]["message"]

            if "tool_calls" in message and message["tool_calls"]:
                print(f"\n✅ 成功调用工具")
                for tc in message["tool_calls"]:
                    print(f"  工具: {tc['function']['name']}")
                    print(f"  参数: {tc['function']['arguments']}")
                return True
            else:
                print(f"\n❌ 没有调用工具")
                print(f"回答: {message.get('content', '')}")
                return False
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False

def test_with_system_message():
    """测试带系统消息的情况"""
    print("\n" + "=" * 80)
    print("测试场景 2: 带系统消息")
    print("=" * 80)

    # 添加系统消息（Codex 可能会加）
    messages = [
        {
            "role": "system",
            "content": "你是一个有帮助的AI助手。当用户需要实时信息时，你应该使用搜索工具。"
        },
        {"role": "user", "content": "搜索一下AMD的股价"}
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 2000
    }

    print(f"\nMessages: {len(messages)} 条消息")
    print(f"  - System: {messages[0]['content'][:60]}...")
    print(f"  - User: {messages[1]['content']}")

    try:
        response = httpx.post(VLLM_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            message = data["choices"][0]["message"]

            if "tool_calls" in message and message["tool_calls"]:
                print(f"\n✅ 成功调用工具")
                return True
            else:
                print(f"\n❌ 没有调用工具")
                print(f"回答: {message.get('content', '')}")
                return False
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False

def test_negative_context():
    """测试负面上下文（之前失败过）"""
    print("\n" + "=" * 80)
    print("测试场景 3: 负面上下文（之前查询失败）")
    print("=" * 80)

    # 模拟之前查询失败的情况
    messages = [
        {"role": "user", "content": "查询一下AMD的股价"},
        {"role": "assistant", "content": "抱歉，我暂时查不到 AMD 的股价，你可以打开股票软件或者搜索引擎看看。"},
        {"role": "user", "content": "那帮我搜索一下AMD的股价"}  # 再次尝试
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 2000
    }

    print(f"\nMessages: {len(messages)} 条消息")
    print(f"  (模拟之前失败，用户再次请求)")

    try:
        response = httpx.post(VLLM_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            message = data["choices"][0]["message"]

            if "tool_calls" in message and message["tool_calls"]:
                print(f"\n✅ 这次成功调用工具（之前失败不影响）")
                return True
            else:
                print(f"\n❌ 仍然没有调用工具")
                print(f"回答: {message.get('content', '')}")
                print(f"\n⚠️  负面上下文可能影响了模型判断！")
                return False
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False

def test_with_long_context():
    """测试长上下文"""
    print("\n" + "=" * 80)
    print("测试场景 4: 长对话历史（10+ 轮）")
    print("=" * 80)

    # 模拟多轮对话
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
        {"role": "user", "content": "今天天气怎么样"},
        {"role": "assistant", "content": "我可以帮你查询天气。"},
        {"role": "user", "content": "上海的天气"},
        {"role": "assistant", "content": "上海今天晴天。"},
        {"role": "user", "content": "NBA最近有什么比赛"},
        {"role": "assistant", "content": "NBA赛程可以搜索查看。"},
        {"role": "user", "content": "好的"},
        {"role": "assistant", "content": "还有什么可以帮你的吗？"},
        {"role": "user", "content": "搜索一下AMD的股价"}  # 第11轮
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 2000
    }

    print(f"\nMessages: {len(messages)} 条消息（长对话）")

    try:
        response = httpx.post(VLLM_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            message = data["choices"][0]["message"]

            if "tool_calls" in message and message["tool_calls"]:
                print(f"\n✅ 长对话不影响工具调用")
                return True
            else:
                print(f"\n❌ 长对话中没有调用工具")
                print(f"回答: {message.get('content', '')}")
                return False
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False

def main():
    print("\n" + "=" * 80)
    print("AMD 股价搜索 - 带上下文测试")
    print("=" * 80)

    results = {}
    results["历史对话"] = test_with_history()
    results["系统消息"] = test_with_system_message()
    results["负面上下文"] = test_negative_context()
    results["长对话"] = test_with_long_context()

    print("\n" + "=" * 80)
    print("总结")
    print("=" * 80)

    success_count = sum(1 for v in results.values() if v)
    print(f"\n通过: {success_count}/{len(results)} 个场景")

    for scene, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {scene}")

    if not results["负面上下文"]:
        print(f"\n🚨 发现关键问题：负面上下文影响了工具调用！")
        print(f"\n解决方案：")
        print(f"  1. 清除或重置对话历史")
        print(f"  2. 在系统消息中强调使用工具")
        print(f"  3. 使用更激进的tool_choice（'required'）")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
