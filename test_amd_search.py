#!/usr/bin/env python3
"""
AMD股价搜索完整测试脚本
模拟从用户输入到vLLM调用的完整流程
"""

import json
import httpx

# 配置
VLLM_URL = "http://localhost:8102/v1/chat/completions"
SEARXNG_URL = "http://localhost:28080/search"

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

def test_vllm_tool_call():
    """测试 vLLM 是否会调用 web_search 工具"""
    print("=" * 80)
    print("测试 1: vLLM 工具调用")
    print("=" * 80)

    # 构造消息
    messages = [
        {"role": "user", "content": "搜索一下AMD的股价"}
    ]

    # 调用 vLLM
    payload = {
        "model": "/home/xilinx/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-W4A16-llmcompressor",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "max_tokens": 2000
    }

    print(f"\n发送请求到 vLLM...")
    print(f"Messages: {json.dumps(messages, ensure_ascii=False)}")
    print(f"Tools: {len(tools)} 个工具")
    print(f"  - weather")
    print(f"  - web_search (包含'股价'关键词)")

    try:
        response = httpx.post(VLLM_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]

            print(f"\n✅ vLLM 响应成功")
            print(f"Finish reason: {choice['finish_reason']}")

            if "tool_calls" in message and message["tool_calls"]:
                print(f"\n🎉 成功！vLLM 调用了工具:")
                for tc in message["tool_calls"]:
                    print(f"  - 工具: {tc['function']['name']}")
                    print(f"    参数: {tc['function']['arguments']}")
                return True, message["tool_calls"]
            else:
                print(f"\n❌ 失败！vLLM 没有调用工具")
                print(f"直接回答: {message.get('content', '')}")
                return False, None
        else:
            print(f"\n❌ vLLM 请求失败: {response.status_code}")
            print(response.text)
            return False, None
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False, None

def test_searxng():
    """测试 SearxNG 搜索"""
    print("\n" + "=" * 80)
    print("测试 2: SearxNG 搜索")
    print("=" * 80)

    query = "AMD 股价"
    print(f"\n搜索关键词: '{query}'")

    try:
        response = httpx.get(SEARXNG_URL, params={"q": query, "format": "json"}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            all_results = data.get("results", [])

            print(f"\n✅ SearxNG 返回 {len(all_results)} 个结果")

            # 应用过滤逻辑
            valid_results = []
            for r in all_results[:15]:
                content = r.get("content", "").strip()
                if content and len(content) > 10:
                    if ("doesn't work properly without JavaScript" in content or
                        "cannot provide a description" in content):
                        continue
                    valid_results.append(r)
                    if len(valid_results) >= 5:
                        break

            print(f"过滤后有效结果: {len(valid_results)} 个")

            if valid_results:
                print(f"\n前 {len(valid_results)} 个有效结果:")
                for i, r in enumerate(valid_results, 1):
                    title = r.get("title", "")
                    content = r.get("content", "")[:150]
                    print(f"\n{i}. {title}")
                    print(f"   {content}...")

                # 检查是否包含价格信息
                has_price = any("股价" in r.get("title", "") or "股价" in r.get("content", "") or
                               "price" in r.get("content", "").lower() or
                               "$" in r.get("content", "") or
                               "¥" in r.get("content", "") or
                               any(char.isdigit() for char in r.get("content", "")[:100])
                               for r in valid_results)

                if has_price:
                    print(f"\n✅ 结果中包含价格相关信息")
                else:
                    print(f"\n⚠️  结果中可能不包含具体价格")

                return True, valid_results
            else:
                print(f"\n❌ 没有有效结果")
                return False, []
        else:
            print(f"\n❌ SearxNG 请求失败: {response.status_code}")
            return False, []
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        return False, []

def test_different_prompts():
    """测试不同的用户输入"""
    print("\n" + "=" * 80)
    print("测试 3: 不同的用户输入")
    print("=" * 80)

    test_prompts = [
        "搜索一下AMD的股价",
        "帮我搜索AMD股价",
        "查询AMD的股票价格",
        "AMD股票多少钱",
        "查一下AMD stock price",
    ]

    results = {}

    for prompt in test_prompts:
        print(f"\n测试输入: '{prompt}'")
        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": "/home/xilinx/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-W4A16-llmcompressor",
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 2000
        }

        try:
            response = httpx.post(VLLM_URL, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                message = data["choices"][0]["message"]

                if "tool_calls" in message and message["tool_calls"]:
                    tool_name = message["tool_calls"][0]["function"]["name"]
                    print(f"  ✅ 调用了工具: {tool_name}")
                    results[prompt] = "success"
                else:
                    print(f"  ❌ 没有调用工具")
                    print(f"     回答: {message.get('content', '')[:50]}...")
                    results[prompt] = "failed"
            else:
                print(f"  ❌ 请求失败: {response.status_code}")
                results[prompt] = "error"
        except Exception as e:
            print(f"  ❌ 异常: {e}")
            results[prompt] = "error"

    # 统计
    success_count = sum(1 for v in results.values() if v == "success")
    print(f"\n总结: {success_count}/{len(test_prompts)} 个输入成功调用工具")

    return results

def main():
    print("\n" + "=" * 80)
    print("AMD 股价搜索完整测试")
    print("=" * 80)

    # 测试 1: vLLM 工具调用
    tool_called, tool_calls = test_vllm_tool_call()

    # 测试 2: SearxNG 搜索
    search_success, search_results = test_searxng()

    # 测试 3: 不同输入
    prompt_results = test_different_prompts()

    # 最终总结
    print("\n" + "=" * 80)
    print("最终总结")
    print("=" * 80)

    print(f"\n1. vLLM 工具调用: {'✅ 成功' if tool_called else '❌ 失败'}")
    print(f"2. SearxNG 搜索: {'✅ 成功' if search_success else '❌ 失败'}")
    print(f"3. 多种输入测试: {sum(1 for v in prompt_results.values() if v == 'success')}/{len(prompt_results)} 成功")

    if tool_called and search_success:
        print(f"\n🎉 所有测试通过！系统工作正常")
    elif tool_called and not search_success:
        print(f"\n⚠️  工具调用成功，但搜索结果质量差")
    elif not tool_called and search_success:
        print(f"\n❌ 关键问题：vLLM 不调用工具！")
        print(f"\n可能原因:")
        print(f"  1. 工具描述不够明确（虽然已包含'股价'）")
        print(f"  2. Qwen 模型对某些词汇有特殊处理")
        print(f"  3. 温度参数或其他配置问题")
        print(f"\n建议:")
        print(f"  1. 尝试更激进的工具描述")
        print(f"  2. 添加系统提示强制使用工具")
        print(f"  3. 测试其他关键词（'价格'、'行情'）")
    else:
        print(f"\n❌ 多个环节失败，需要全面排查")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
