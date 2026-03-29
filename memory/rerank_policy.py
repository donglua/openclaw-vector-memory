# memory/rerank_policy.py
"""纯决策逻辑：是否触发 rerank，以及如何合并重排结果"""
from __future__ import annotations


def should_rerank(
    *,
    scores: list[float],
    top_k: int,
    min_candidates: int,
    flat_gap_threshold: float,
    low_conf_threshold: float,
    force: bool,
) -> tuple[bool, str]:
    """判断是否应触发 LLM 重排"""
    if force:
        return True, "force"
    if len(scores) < min_candidates or len(scores) < top_k:
        return False, "insufficient_candidates"

    top1 = scores[0]
    kth = scores[min(top_k, len(scores)) - 1]
    if (top1 - kth) < flat_gap_threshold:
        return True, "flat_gap"
    if top1 < low_conf_threshold:
        return True, "low_conf"
    return False, "high_conf"


def merge_reranked_candidates(
    *,
    candidates: list[dict],
    reranked_indices: list[int],
    top_k: int,
) -> list[dict]:
    """将 LLM 返回的索引合并/去重/补齐，返回最终 top_k 结果"""
    valid = []
    seen = set()

    for idx in reranked_indices:
        if 0 <= idx < len(candidates) and idx not in seen:
            valid.append(idx)
            seen.add(idx)

    # 补齐未出现的候选（保持原始顺序）
    for idx in range(len(candidates)):
        if idx not in seen:
            valid.append(idx)

    final_indices = valid[:top_k]
    return [candidates[i] for i in final_indices]
