# openclaw-vector-memory

> OpenClaw 记忆系统增强版：基于 Zilliz Cloud 的向量搜索，支持本地与远程 Embedding API。

## 特性

- **灵活后端**：支持任意 OpenAI 兼容的远程 API（硅基流动、OpenAI等），或本地模型（如 BGE-M3）
- **混合搜索**：若使用本地 BGE-M3，可同时输出 Dense（语义）+ Sparse（关键词）向量，实现 RRF 融合排序
- **云端持久化**：Zilliz Cloud 免费层存储，多端同步，开箱即用

## 快速开始

### 1. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入 Zilliz Cloud 的 URI 和 Token，以及 Embedding 后端配置。

**用本地模型（默认 BGE-M3，支持混合搜索）：**
```bash
EMBEDDING_PROVIDER=local
# 【可选】可指定其他本地模型路径，或保留默认的 BAAI/bge-m3
EMBEDDING_MODEL=BAAI/bge-m3
```
首次运行自动下载模型（约 2GB），如果指定了本地已经下载好的权重路径，则可实现完全离线加载。原生支持 Dense+Sparse 双路召回。

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
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_DIM=4096
```

常见服务配置对照：

| 服务 | `EMBEDDING_API_BASE` | `EMBEDDING_MODEL` | `EMBEDDING_DIM` |
|------|---------------------|------------------|----------------|
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen3-Embedding-8B` | `4096` |
| OpenAI | `https://api.openai.com/v1` | `text-embedding-3-small` | `1536` |
| Ollama（本地服务） | `http://localhost:11434/v1` | `nomic-embed-text` | `768` |

> 远程 API 仅返回 Dense 向量，自动降级为语义搜索（无 Sparse），对个人记忆场景影响不大。

### 3. 测试

```bash
python3 main.py --test
```

## CLI 用法

```bash
# 写入一条记忆
python3 main.py --save "用户喜欢用 Python，讨厌 Java"

# 语义搜索
python3 main.py --search "这个用户有什么编程习惯"

# 从 MEMORY.md 迁移已有记忆
python3 main.py --migrate /path/to/MEMORY.md

# 查看记忆总条数
python3 main.py --count
```

## 集成到 OpenClaw

本项目提供了一键安装脚本，能直接把 `memory` 模块、依赖和 `.env` 配置注入到你的 OpenClaw 项目中：

```bash
# 假设你的 OpenClaw 项目路径是 ~/workspace/openclaw
./install.sh ~/workspace/openclaw
```

在安装最后一步，脚本会自动在目标目录的 `AGENTS.md` 中追加下面这段控制指令，引导你的主 Agent 自动使用：

```markdown
# 🧠 长期向量记忆库 (自动注入)
**核心指令**：不要直接读取或写入传统的 `MEMORY.md` 文件。对于用户的偏好、长期记忆、以及背景上下文，请使用以下向量搜索工具：
1. **检索记忆**：当你需要回忆关于用户的信息时，使用终端执行：
   `python3 vector_memory.py --search "你要检索的关键语义"`
2. **保存记忆**：当用户告知你全新的偏好或长期有效的事实，使用终端执行：
   `python3 vector_memory.py --save "清晰且完整的记忆内容"`
```

以后你的 Agent 会自动通过执行脚本来调取或覆盖长篇大论的旧记忆！

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

## 注意与警告（⚠️ 必看）

### ⚠️ 关于模型维度与不可切换的问题

**向量数据库的集合（Collection）一旦被创建投用，其“维度大小（Dimension）就会被永久锁定”！**

1. **绝对不可中途“混合使用”**：不能在同一个 `COLLECTION_NAME` 中给它分别塞入 1024 维（如 BGE-M3）和 4096 维（如 Qwen3）的不同记忆。如果我们在 `.env` 中更换为 4096 维模型，继续向 1024 维的旧库里写入数据，**程序会直接当场崩溃报错**。
2. **正确的心智模型：从一而终**。建议一旦选定（大部分情况下选择默认极速省空间的 1024 维 BGE-M3），不要再随意更换。
3. **如必须更换的正确做法**：遇到必须要换模型的场景，请打开 `.env` 配置文件，给 `COLLECTION_NAME` 换个名字（例如从 `openclaw_memories` 修改为 `openclaw_memories_qwen`），这样 Zilliz 就会为你建一张崭新干净的新表。**注意，这意味着你在旧表里的所有旧记忆，需要用旧模型读取出来，再用新模型重新写入翻译一遍，才能进行所谓的“迁移”。**

---
- 本地模式支持完整混合搜索（Dense + Sparse）；远程 API 仅 Dense 搜索，`store.py` 自动降级
- Zilliz Cloud 免费层：1 个 Cluster，1GB 存储，足够个人长期使用
