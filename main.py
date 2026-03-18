"""
OpenClaw 向量记忆 CLI 入口

用法：
    python main.py --save "用户喜欢用 Python"
    python main.py --search "用户有什么编程习惯"
    python main.py --migrate path/to/MEMORY.md
    python main.py --test
    python main.py --count
"""

import argparse
import sys
from memory.store import MemoryStore


def get_store() -> MemoryStore:
    """初始化存储，配置从 .env 文件读取"""
    try:
        return MemoryStore()
    except KeyError as e:
        print(f"❌ 缺少环境变量 {e}，请复制 .env.example 为 .env 并填入配置")
        sys.exit(1)


def cmd_save(text: str):
    store = get_store()
    store.save(text, source="cli")
    print(f"✅ 已保存记忆：{text}")


def cmd_search(query: str, top_k: int = 5):
    store = get_store()
    hits = store.search(query, top_k=top_k)
    if not hits:
        print("❌ 未找到相关记忆")
        return
    print(f"\n🔍 查询：{query}\n")
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] 得分: {h['score']:.4f} | 来源: {h['source']}")
        print(f"      {h['text']}\n")


def cmd_migrate(md_path: str):
    from memory.migrate import migrate_markdown
    store = get_store()
    migrate_markdown(md_path, store)


def cmd_count():
    store = get_store()
    n = store.count()
    print(f"📊 当前记忆库中共有 {n} 条记忆")


def cmd_test():
    """内置测试，验证 BGE-M3 + Zilliz Cloud 端到端能否正常工作"""
    print("=== OpenClaw 向量记忆测试 ===\n")
    store = get_store()

    # 写入测试记忆
    test_text = "用户喜欢用 Python，讨厌 Java，偏好简洁代码风格"
    print(f"[1/3] 写入测试记忆：{test_text}")
    store.save(test_text, source="test", tags=["preference"])
    print("      写入成功\n")

    # 搜索测试
    query = "这个用户喜欢什么编程语言"
    print(f"[2/3] 搜索：{query}")
    hits = store.search(query, top_k=3)
    print(f"      返回 {len(hits)} 条结果")
    for h in hits:
        print(f"      得分 {h['score']:.4f} | {h['text'][:60]}")
    print()

    # 验证召回
    found = any(test_text in h["text"] for h in hits)
    if found:
        print("[3/3] ✅ 测试通过：成功召回刚写入的记忆")
    else:
        print("[3/3] ⚠️  未在 Top-3 中找到刚写入的记忆（可能需等待索引刷新，再次运行试试）")

    # Prompt 片段示例
    print("\n--- build_prompt_context 示例 ---")
    context = store.build_prompt_context(query)
    print(context)


def main():
    parser = argparse.ArgumentParser(description="OpenClaw 向量记忆 CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save", metavar="TEXT", help="写入一条记忆")
    group.add_argument("--search", metavar="QUERY", help="语义搜索记忆")
    group.add_argument("--migrate", metavar="MD_PATH", help="从 Markdown 文件迁移记忆")
    group.add_argument("--count", action="store_true", help="查看记忆总条数")
    group.add_argument("--test", action="store_true", help="运行端到端测试")

    parser.add_argument("--top-k", type=int, default=5, help="搜索返回条数（默认 5）")

    args = parser.parse_args()

    if args.save:
        cmd_save(args.save)
    elif args.search:
        cmd_search(args.search, top_k=args.top_k)
    elif args.migrate:
        cmd_migrate(args.migrate)
    elif args.count:
        cmd_count()
    elif args.test:
        cmd_test()


if __name__ == "__main__":
    main()
