# openclaw-vector-memory

> OpenClaw 记忆系统增强版：基于 Zilliz Cloud 的向量搜索，支持本地与远程 Embedding API。

## 特性

- **灵活后端**：支持任意 OpenAI 兼容的远程 API（硅基流动、OpenAI等），或本地模型（如 BGE-M3）
- **混合搜索**：若使用本地 BGE-M3，可同时输出 Dense（语义）+ Sparse（关键词）向量，实现 RRF 融合排序
- **云端持久化**：Zilliz Cloud 免费层存储，多端同步，开箱即用

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

**用本地模型（默认 BGE-M3，支持混合搜索）：**
```bash
EMBEDDING_PROVIDER=local
```
首次运行自动下载模型（约 2GB），之后离线可用，原生支持 Dense+Sparse 双路召回。

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

本项目提供了一键安装脚本，能直接把 `memory` 模块、依赖和 `.env` 配置注入到你的 OpenClaw 项目中：

```bash
# 假设你的 OpenClaw 项目路径是 ~/workspace/openclaw
./install.sh ~/workspace/openclaw
```

安装完成后，进入你的 OpenClaw 目录，执行 `pip install -r requirements.txt`，并在 `.env` 里配置 Zilliz 密钥。

在 OpenClaw 源码里（如 `agent.py`），直接这样用：

```python
from memory import MemoryStore

store = MemoryStore()

# 替换原来的追加文件逻辑
store.save("用户今天询问了 Python 异步编程的问题")

# 替换原来读取 MEMORY.md 的逻辑，获取 Top-K 记忆并拼入 Prompt
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
