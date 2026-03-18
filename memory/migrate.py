"""
从现有 MEMORY.md 迁移记忆到 Zilliz Cloud 向量库

使用方式：
    from memory.migrate import migrate_markdown
    migrate_markdown("path/to/MEMORY.md", store)

或通过 CLI：
    python main.py --migrate path/to/MEMORY.md
"""

from __future__ import annotations
import re
from pathlib import Path
from .store import MemoryStore


def _split_chunks(text: str, min_len: int = 20) -> list[str]:
    """
    按段落（空行）分块，过滤太短的片段
    同时去掉 Markdown 标题行（#开头）作为独立 chunk，但保留内容
    """
    # 先按双换行切段落
    raw_chunks = re.split(r"\n{2,}", text.strip())
    chunks = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        # 跳过纯标题行和太短的片段
        if not chunk or len(chunk) < min_len:
            continue
        chunks.append(chunk)
    return chunks


def migrate_markdown(md_path: str, store: MemoryStore, batch_size: int = 32) -> int:
    """
    将 Markdown 文件中的记忆批量导入向量库

    Args:
        md_path:    Markdown 文件路径
        store:      MemoryStore 实例
        batch_size: 每批处理数量

    Returns:
        成功写入的记忆条数
    """
    path = Path(md_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{md_path}")

    text = path.read_text(encoding="utf-8")
    chunks = _split_chunks(text)

    if not chunks:
        print("⚠️  未找到有效内容")
        return 0

    total = len(chunks)
    print(f"📄 共解析出 {total} 条记忆块，开始写入...")

    done = 0
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        store.save_batch(batch, source=f"migrate:{path.name}")
        done += len(batch)
        print(f"   已写入 {done}/{total}")

    print(f"✅ 迁移完成，共写入 {done} 条")
    return done
