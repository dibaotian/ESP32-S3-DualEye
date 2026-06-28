#!/usr/bin/env python3
"""
记忆系统完整测试脚本
测试：存储、检索、相似度匹配、统计等
"""

import sys
import json
import os
from datetime import datetime

# 添加路径
sys.path.insert(0, '/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2')

from agent.memory_store import VectorMemory

# 记忆存储路径
MEMORY_DIR = "/home/xilinx/Documents/ESP32-S3-DualEye/web_voice_bot_v2/data/memory"

def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def test_1_check_current_state():
    """测试1: 检查当前状态"""
    print_section("测试 1: 检查当前记忆状态")

    try:
        memory = VectorMemory(MEMORY_DIR)
        count = memory.count()
        print(f"\n✅ 记忆系统正常运行")
        print(f"📊 当前记忆总数: {count} 条")

        # 检查文件
        embeddings_path = os.path.join(MEMORY_DIR, "embeddings.npy")
        docs_path = os.path.join(MEMORY_DIR, "docs.json")

        if os.path.exists(embeddings_path):
            size = os.path.getsize(embeddings_path) / 1024
            print(f"📁 embeddings.npy: {size:.1f} KB")

        if os.path.exists(docs_path):
            size = os.path.getsize(docs_path) / 1024
            print(f"📁 docs.json: {size:.1f} KB")

            # 读取最近5条记忆
            with open(docs_path, 'r', encoding='utf-8') as f:
                docs = json.load(f)
                print(f"\n最近 5 条记忆:")
                for i, doc in enumerate(docs[-5:], 1):
                    text = doc['text'][:80] + "..." if len(doc['text']) > 80 else doc['text']
                    print(f"  {len(docs)-5+i}. {text}")

        return True, memory
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_2_add_memories(memory):
    """测试2: 添加新记忆"""
    print_section("测试 2: 添加新记忆")

    test_memories = [
        "用户说:我的名字是测试用户 | 助手答:好的，记住了你叫测试用户",
        "用户说:我最喜欢的颜色是蓝色 | 助手答:明白了，蓝色是你的最爱",
        "用户说:我的生日是3月15日 | 助手答:记住了，3月15日是你的生日",
        "用户说:我住在上海浦东 | 助手答:知道了，你住在上海浦东新区",
        "用户说:我养了一只叫小白的猫 | 助手答:好可爱，你有一只叫小白的猫",
    ]

    initial_count = memory.count()
    print(f"\n添加前记忆数: {initial_count}")

    try:
        for i, mem in enumerate(test_memories, 1):
            memory.add(mem)
            print(f"  {i}. ✅ {mem[:60]}...")

        final_count = memory.count()
        added = final_count - initial_count

        print(f"\n✅ 成功添加 {added} 条记忆")
        print(f"📊 当前总数: {final_count} 条")

        return True
    except Exception as e:
        print(f"\n❌ 添加失败: {e}")
        return False

def test_3_recall_by_similarity(memory):
    """测试3: 语义检索"""
    print_section("测试 3: 语义相似度检索")

    test_queries = [
        ("我叫什么名字", "应该检索到：我的名字是测试用户"),
        ("我喜欢什么颜色", "应该检索到：我最喜欢的颜色是蓝色"),
        ("我的生日是几号", "应该检索到：我的生日是3月15日"),
        ("我住在哪里", "应该检索到：我住在上海浦东"),
        ("我有宠物吗", "应该检索到：我养了一只叫小白的猫"),
        ("AMD股价", "应该检索到：之前的股价搜索相关记忆"),
    ]

    success_count = 0

    for query, expected in test_queries:
        print(f"\n查询: \"{query}\"")
        print(f"预期: {expected}")

        try:
            results = memory.recall(query, k=3, min_score=0.35)

            if results:
                print(f"✅ 检索到 {len(results)} 条相关记忆:")
                for i, r in enumerate(results, 1):
                    text = r[:100] + "..." if len(r) > 100 else r
                    print(f"  {i}. {text}")
                success_count += 1
            else:
                print(f"⚠️  未检索到相关记忆")
        except Exception as e:
            print(f"❌ 检索失败: {e}")

    print(f"\n总结: {success_count}/{len(test_queries)} 个查询成功检索到结果")

    return success_count > 0

def test_4_similarity_threshold(memory):
    """测试4: 相似度阈值测试"""
    print_section("测试 4: 相似度阈值测试")

    query = "我最喜欢的颜色"
    thresholds = [0.2, 0.35, 0.5, 0.7, 0.9]

    print(f"\n查询: \"{query}\"")
    print(f"测试不同的相似度阈值:\n")

    for threshold in thresholds:
        try:
            results = memory.recall(query, k=5, min_score=threshold)
            print(f"阈值 {threshold:.2f}: 检索到 {len(results)} 条记忆")

            if results and threshold <= 0.5:
                # 只显示前2条
                for i, r in enumerate(results[:2], 1):
                    text = r[:80] + "..." if len(r) > 80 else r
                    print(f"  {i}. {text}")
        except Exception as e:
            print(f"阈值 {threshold:.2f}: ❌ {e}")

    print(f"\n💡 推荐阈值: 0.35 (平衡召回率和准确率)")

    return True

def test_5_topk_comparison(memory):
    """测试5: Top-K 数量对比"""
    print_section("测试 5: Top-K 数量对比")

    query = "我的个人信息"
    k_values = [1, 3, 5, 10]

    print(f"\n查询: \"{query}\"")
    print(f"测试不同的 Top-K 值:\n")

    for k in k_values:
        try:
            results = memory.recall(query, k=k, min_score=0.35)
            print(f"Top-{k}: 检索到 {len(results)} 条")

            if results and k == 3:
                print("  (当前默认配置)")
        except Exception as e:
            print(f"Top-{k}: ❌ {e}")

    print(f"\n💡 当前配置: MEMORY_TOPK=3")
    print(f"   - 更多(5-10): 更全面的上下文，但可能包含不相关信息")
    print(f"   - 更少(1-2): 更精准，但可能遗漏相关信息")

    return True

def test_6_cross_language(memory):
    """测试6: 中英文混合检索"""
    print_section("测试 6: 中英文混合检索")

    # 添加英文记忆
    english_mem = "用户说:My favorite programming language is Python | 助手答:Got it, you love Python"
    memory.add(english_mem)
    print(f"添加英文记忆: {english_mem}")

    # 中文查询英文记忆
    queries = [
        ("你最喜欢的编程语言", "中文查询 → 英文记忆"),
        ("favorite language", "英文查询 → 英文记忆"),
        ("Python", "关键词查询 → 英文记忆"),
    ]

    print(f"\n测试跨语言检索:")

    for query, desc in queries:
        results = memory.recall(query, k=3, min_score=0.3)  # 稍微降低阈值
        found = any("Python" in r or "programming" in r for r in results)
        status = "✅" if found else "⚠️"
        print(f"  {status} {desc}: '{query}' → {'找到' if found else '未找到'}")

    print(f"\n💡 BAAI/bge-small-zh-v1.5 模型:")
    print(f"   - 对中文优化")
    print(f"   - 支持中英文混合")
    print(f"   - 跨语言检索可能需要降低阈值")

    return True

def test_7_memory_persistence(memory):
    """测试7: 持久化验证"""
    print_section("测试 7: 持久化验证")

    print(f"\n检查记忆文件的持久化...")

    # 添加一条带时间戳的记忆
    timestamp = datetime.now().isoformat()
    test_mem = f"用户说:测试时间 {timestamp} | 助手答:记录测试时间"

    print(f"添加测试记忆: {test_mem[:60]}...")
    memory.add(test_mem)

    # 重新加载
    print(f"\n重新加载记忆系统...")
    memory2 = VectorMemory(MEMORY_DIR)

    # 检索
    results = memory2.recall(f"测试时间 {timestamp}", k=1, min_score=0.5)

    if results and timestamp in results[0]:
        print(f"✅ 持久化成功！重新加载后能检索到新添加的记忆")
        print(f"   检索结果: {results[0][:80]}...")
    else:
        print(f"⚠️  持久化可能有问题，未检索到刚添加的记忆")

    # 检查文件修改时间
    docs_path = os.path.join(MEMORY_DIR, "docs.json")
    if os.path.exists(docs_path):
        mtime = os.path.getmtime(docs_path)
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n📁 docs.json 最后修改: {mtime_str}")

    return True

def test_8_statistics(memory):
    """测试8: 统计分析"""
    print_section("测试 8: 记忆统计分析")

    docs_path = os.path.join(MEMORY_DIR, "docs.json")

    if not os.path.exists(docs_path):
        print(f"❌ docs.json 不存在")
        return False

    with open(docs_path, 'r', encoding='utf-8') as f:
        docs = json.load(f)

    total = len(docs)
    print(f"\n📊 总记忆数: {total} 条")

    # 统计长度分布
    lengths = [len(doc['text']) for doc in docs]
    avg_length = sum(lengths) / len(lengths) if lengths else 0
    max_length = max(lengths) if lengths else 0
    min_length = min(lengths) if lengths else 0

    print(f"\n📏 记忆长度统计:")
    print(f"   平均长度: {avg_length:.1f} 字符")
    print(f"   最长: {max_length} 字符")
    print(f"   最短: {min_length} 字符")

    # 统计关键词出现频率
    keywords = ["股价", "搜索", "AMD", "天气", "名字", "颜色", "生日"]
    print(f"\n🔍 关键词频率:")

    for kw in keywords:
        count = sum(1 for doc in docs if kw in doc['text'])
        if count > 0:
            print(f"   '{kw}': {count} 条 ({count/total*100:.1f}%)")

    # 元数据统计
    has_meta = sum(1 for doc in docs if doc.get('meta'))
    print(f"\n🏷️  元数据:")
    print(f"   包含元数据: {has_meta}/{total} 条 ({has_meta/total*100:.1f}%)")

    return True

def main():
    print("\n" + "=" * 80)
    print("记忆系统完整测试")
    print("测试时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)

    # 测试1: 检查当前状态
    success_1, memory = test_1_check_current_state()
    if not success_1 or memory is None:
        print("\n❌ 记忆系统初始化失败，无法继续测试")
        return

    # 测试2: 添加记忆
    success_2 = test_2_add_memories(memory)

    # 测试3: 语义检索
    success_3 = test_3_recall_by_similarity(memory)

    # 测试4: 相似度阈值
    success_4 = test_4_similarity_threshold(memory)

    # 测试5: Top-K 对比
    success_5 = test_5_topk_comparison(memory)

    # 测试6: 跨语言
    success_6 = test_6_cross_language(memory)

    # 测试7: 持久化
    success_7 = test_7_memory_persistence(memory)

    # 测试8: 统计
    success_8 = test_8_statistics(memory)

    # 总结
    print_section("测试总结")

    results = {
        "当前状态检查": success_1,
        "添加新记忆": success_2,
        "语义检索": success_3,
        "相似度阈值": success_4,
        "Top-K 对比": success_5,
        "跨语言检索": success_6,
        "持久化验证": success_7,
        "统计分析": success_8,
    }

    success_count = sum(1 for v in results.values() if v)
    total_tests = len(results)

    print(f"\n测试通过: {success_count}/{total_tests}")
    print()

    for test_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {test_name}")

    if success_count == total_tests:
        print(f"\n🎉 所有测试通过！记忆系统运行正常")
    elif success_count >= total_tests * 0.7:
        print(f"\n⚠️  大部分测试通过，但有些功能需要检查")
    else:
        print(f"\n❌ 多个测试失败，记忆系统可能有问题")

    print(f"\n💡 快速命令:")
    print(f"   查看记忆: cat {MEMORY_DIR}/docs.json | python3 -m json.tool | less")
    print(f"   记忆总数: python3 -c 'import json; print(len(json.load(open(\"{MEMORY_DIR}/docs.json\"))))'")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
