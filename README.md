# openclaw-vector-memory

> OpenClaw 记忆系统增强版：BGE-M3 + Zilliz Cloud 向量搜索，支持本地与远程 Embedding API。

## 特性

- **混合搜索**：本地 BGE-M3 同时输出 Dense（语义）+ Sparse（关键词）向量，RRF 融合排序
- **中文友好**：BGE-M3 对中文有专项优化
- **灵活后端**：本地模型或任意 OpenAI 兼容 API，`.env` 一行切换
- **云端持久化**：Zilliz Cloud 免费层存储，多端同步

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入 Zilliz Cloud 的 URI 和 Token，以及 Embedding 后端配置。

**用本地 BGE-M3（默认，推荐）：**
```bash
EMBEDDING_PROVIDER=local
```
首次运行自动下载模型（约 2GB），之后离线可用。

**用远程 API（硅基流动 / OpenAI / 任意兼容接口）：**

完整 `.env` 示例（以硅基流动为例）：
```bash
# Zilliz Cloud
ZILLIZ_URI=https://your-cluster-id.api.gcp-us-west1.zillizcloud.com
ZILLIZ_TOKEN=your_token_here
COLLECTION_NAME=openclaw_memories

# 远程 Embedding API
EMBEDDING_PROVIDER=remote
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
```

常见服务配置对照：

| 服务 | `EMBEDDING_API_BASE` | `EMBEDDING_MODEL` | `EMBEDDING_DIM` |
|------|---------------------|------------------|----------------|
| 硅基流动 | `https://api.siliconflow.cn/v1` | `BAAI/bge-m3` | `1024` |
| OpenAI | `https://api.openai.com/v1` | `text-embedding-3-small` | `1536` |
| Ollama（本地服务） | `http://localhost:11434/v1` | `nomic-embed-text` | `768` |

> 远程 API 仅返回 Dense 向量，自动降级为语义搜索（无 Sparse），对个人记忆场景影响不大。

### 3. 测试

```bash
python main.py --test
```

## CLI 用法

```bash
# 写入一条记忆
python main.py --save "用户喜欢用 Python，讨厌 Java"

# 语义搜索
python main.py --search "这个用户有什么编程习惯"

# 从 MEMORY.md 迁移已有记忆
python main.py --migrate /path/to/MEMORY.md

# 查看记忆总条数
python main.py --count
```

## 集成到 OpenClaw

```python
from memory import MemoryStore

store = MemoryStore()

# 写入记忆
store.save("用户今天询问了 Python 异步编程的问题")

# 替换原来读 MEMORY.md 的逻辑，直接生成 Prompt 片段
context = store.build_prompt_context(user_input)
prompt = f"{context}\n\n用户：{user_input}"
```

## 项目结构

```
.
├── requirements.txt
├── .env.example
├── main.py              # CLI 入口
└── memory/
    ├── embedder.py      # Embedding 后端（local / remote）
    ├── store.py         # Zilliz Cloud 读写核心
    └── migrate.py       # 从 MEMORY.md 迁移
```

## 注意

- 本地模式支持完整混合搜索（Dense + Sparse）；远程 API 仅 Dense 搜索，`store.py` 自动降级
- Zilliz Cloud 免费层：1 个 Cluster，1GB 存储，足够个人长期使用
- Embedding 模型一旦选定，切换后需重新写入所有记忆（向量维度/分布不同）
