# OpenClaw 向量记忆系统

> BGE-M3 + Zilliz Cloud 混合向量搜索记忆，替换 OpenClaw 原有 Markdown 文件记忆。

## 功能

- **混合搜索**：BGE-M3 同时生成 Dense（语义）+ Sparse（关键词）向量，经 RRF 融合排序
- **中文友好**：BGE-M3 对中文有专项优化
- **完全离线 Embedding**：BGE-M3 在本地运行，无需 API Key
- **云端持久化**：Zilliz Cloud 免费层存储记忆，多端同步

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 Zilliz Cloud

1. 注册 [Zilliz Cloud](https://cloud.zilliz.com)，免费层即可
2. 创建一个 Cluster，获取 URI 和 API Token
3. 复制配置文件并填入：

```bash
cp .env.example .env
# 编辑 .env，填入你的 ZILLIZ_URI 和 ZILLIZ_TOKEN
```

### 3. 测试是否正常

```bash
python main.py --test
```

## CLI 用法

```bash
# 写入一条记忆
python main.py --save "用户喜欢用 Python，讨厌 Java"

# 语义搜索
python main.py --search "这个用户有什么编程习惯"

# 从现有 MEMORY.md 迁移
python main.py --migrate /path/to/MEMORY.md

# 查看记忆总条数
python main.py --count

# 端到端测试
python main.py --test
```

## 在 OpenClaw Agent 中集成

```python
from memory import MemoryStore

store = MemoryStore()

# 写入新记忆
store.save("用户今天询问了 Python 异步编程的问题")

# 构建 Prompt 上下文（替换原来读 MEMORY.md 的逻辑）
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
    ├── __init__.py
    ├── embedder.py      # BGE-M3 封装（懒加载，单例）
    ├── store.py         # Zilliz Cloud 读写核心
    └── migrate.py       # 从 MEMORY.md 迁移
```

## 注意事项

- BGE-M3 首次运行会下载约 **2GB** 模型文件，之后本地缓存
- 建议 `use_fp16=True`（默认已开启），显著降低内存占用
- Zilliz Cloud 免费层支持 1 个 Cluster，1GB 存储，够个人长期使用
