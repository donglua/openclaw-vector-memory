# Remote Dense 检索效果优化设计（条件触发 LLM Rerank）

- 日期：2026-03-27
- 项目：openclaw-vector-memory
- 适用范围：`EMBEDDING_PROVIDER=remote`（Dense-only 路径）
- 设计状态：已确认，可进入实现规划

## 1. 背景与问题

当前 `remote` 模式仅执行一次 Dense 向量检索，直接返回 Milvus 排序结果。该路径简单稳定，但在以下场景中相关性上限偏低：

1. 候选语义相近但排序靠后，Top-K 可用性不足。
2. 向量距离分布平坦时，首位结果置信度不够高。
3. Prompt 上下文构建依赖 Top-K，排序误差会直接放大到下游回答质量。

本次目标是提高最终返回结果的相关性，优先效果，其次控制延迟与调用成本。

## 2. 目标与非目标

## 2.1 目标

1. 在 `remote` 模式下显著提升最终 Top-K 的相关性。
2. 通过“条件触发”避免无必要的每次重排调用。
3. 保证主检索链路鲁棒：重排失败时自动降级，不影响可用性。
4. 维持现有 CLI 用法兼容，不破坏现有保存与迁移能力。

## 2.2 非目标

1. 不改造 `local`（Dense+Sparse）混合检索路径。
2. 不引入本地 cross-encoder（本期固定 LLM rerank）。
3. 不重做存储 schema，不触碰历史向量数据。

## 3. 方案概览

在 `remote` 检索链路中引入“候选召回 + 条件重排”的两阶段流程：

1. **Stage A：Dense 初召回**
   - 先召回较大候选集 `fetch_k`（例如 40）。
2. **Stage B：触发判定**
   - 根据分数形态和置信度判断是否需要 rerank。
3. **Stage C：LLM 重排（可选）**
   - 仅在触发条件满足时调用 LLM 对候选重排。
4. **Stage D：结果清洗与返回**
   - 校验 rerank 输出并补齐，最终返回 `top_k`。

该方案在效果优先前提下，避免将所有请求都变成“必 rerank”。

## 4. 模块与职责

## 4.1 新增模块

- `memory/reranker.py`
  - 职责：封装 LLM rerank 调用、请求构造、返回解析、超时处理。
  - 输入：`query` + 候选列表（含内部索引、文本、原始分数）。
  - 输出：候选索引的新顺序（按相关性降序）。

## 4.2 现有模块改造

- `memory/store.py`
  - 扩展 `search()` 的 `remote` 分支：
    1. 初召回 `fetch_k`。
    2. 调用 `should_rerank(...)` 规则判断。
    3. 触发则调用 `reranker`，否则直接截断。
    4. 对 rerank 结果执行清洗与补齐。
  - 保持 `local` 分支行为不变。

- `main.py`
  - 可选增加调试参数（例如强制 rerank）用于实验。
  - 默认行为兼容当前 CLI。

## 5. 详细数据流

以 `store.search(query, top_k=5)` 为例：

1. `embedder.embed(query)` 生成 Dense 向量。
2. Milvus Dense 搜索，`limit=fetch_k`，返回候选列表。
3. 若候选数不足最小门槛（例如 `< 8`），跳过 rerank。
4. 计算触发信号：
   - 分数平坦：`score(top1) - score(topk) < flat_gap_threshold`
   - 低置信：`score(top1) < low_conf_threshold`
   - 强制开关：`RERANK_FORCE=true`
5. 触发时调用 LLM rerank，得到排序索引序列。
6. 清洗索引（去重、越界过滤、缺失补齐）。
7. 返回最终 `top_k` 结果，并用于 `build_prompt_context()`。

## 6. 配置设计（.env）

新增或补充以下配置项：

- `RERANK_ENABLED=true`
- `RERANK_PROVIDER=llm`
- `RERANK_MODEL=<model-name>`
- `RERANK_FETCH_K=40`
- `RERANK_TIMEOUT_MS=8000`
- `RERANK_FLAT_GAP_THRESHOLD=0.03`
- `RERANK_LOW_CONF_THRESHOLD=0.45`
- `RERANK_MIN_CANDIDATES=8`
- `RERANK_FORCE=false`
- `RERANK_DEBUG=false`

说明：

1. `top_k` 继续使用 CLI 参数（默认 5），`fetch_k` 由 `RERANK_FETCH_K` 控制，且应保证 `fetch_k >= top_k`。
2. 当 `RERANK_ENABLED=false` 时，`remote` 路径退化为当前单阶段 Dense 行为。

## 7. 错误处理与降级策略

重排层遵循“可失败、主流程不失败”：

1. **调用失败降级**
   - 网络异常、超时、429、服务端错误均直接回退原始 Dense 排序。
2. **输出非法降级**
   - 若返回为空或仅含非法索引，直接回退原排序。
3. **部分非法修复**
   - 对合法索引去重后保留顺序，再按原排序补齐缺失候选，确保输出稳定。
4. **超时保护**
   - 单次 rerank 达到 `RERANK_TIMEOUT_MS` 即终止并降级。

## 8. 可观测性与调试

当 `RERANK_DEBUG=true` 时输出结构化调试信息（stdout 或 logger）：

1. 是否触发 rerank。
2. 触发原因（`flat_gap` / `low_conf` / `force`）。
3. rerank 耗时与是否发生降级。
4. 候选规模与最终返回规模。

默认关闭，避免污染普通 CLI 输出。

## 9. 测试策略与验收标准

## 9.1 单元测试

1. `should_rerank` 判定规则覆盖：平坦、高置信、低置信、候选不足、强制开关。
2. rerank 结果清洗覆盖：重复索引、越界索引、空结果、缺失补齐。
3. 降级逻辑覆盖：超时、异常、非法响应。

## 9.2 集成测试（mock 远程 API）

1. `remote + rerank on`：两阶段流程正确执行。
2. `remote + rerank fail`：自动降级且输出结构保持一致。
3. `remote + rerank off`：行为与旧版一致。

## 9.3 离线效果验收

准备一组标注样本（建议 30 个查询，带期望命中记忆）：

1. 指标：`Recall@5`、`MRR@5`。
2. 验收线：`MRR@5` 相比基线提升至少 15%。
3. 时延约束：P95 查询时延维持在可接受阈值（建议 < 2.5s，依据部署环境可微调）。

## 10. 兼容性与实施边界

1. 不变更向量 schema，避免维度/集合迁移风险。
2. 不影响 `save()`、`save_batch()`、`migrate` 逻辑。
3. `local` 模式保持原有 hybrid_search 路径，不引入行为变化。

## 11. 风险与缓解

1. **延迟上升风险**：通过条件触发 + 超时 + 降级控制。
2. **成本上升风险**：通过触发判定减少无效 rerank 请求。
3. **LLM 输出不稳定风险**：通过索引清洗与补齐保证结果结构稳定。

## 12. 实施入口（下一步）

下一阶段使用 `writing-plans` 产出实现计划，按以下顺序拆解：

1. 配置项与解析。
2. `reranker.py` 模块。
3. `store.py` remote 检索链路重构。
4. 测试补充与回归验证。
5. 文档更新（README 与 `.env.example`）。
