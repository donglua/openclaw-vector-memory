# openclaw-vector-memory (Go 版)

> OpenClaw 记忆系统增强版：零依赖单二进制，无需 Python/pip/venv。

## 与 Python 版的区别

| | Python 版 | Go 版 |
|---|---|---|
| 运行环境 | Python 3.x + pip + venv | **无**，单二进制直接运行 |
| 安装依赖 | `pip install -r requirements.txt` | **不需要** |
| 二进制大小 | N/A (需解释器) | ~8MB |
| Embedding | local (BGE-M3) / remote | **仅 remote**（远程 API） |
| 分发部署 | 复制代码 + 安装依赖 | 复制一个文件即可 |

> **Go 版去掉了本地 BGE-M3 支持**（因为那本质上依赖 PyTorch），仅保留 remote 模式。对实际使用影响为零——remote 模式用硅基流动等 API 更快更稳定。

## 快速开始

### 方式一：下载预编译二进制

从 [Releases](https://github.com/nichuanfang/openclaw-vector-memory/releases) 页面下载对应平台的二进制文件，直接运行。

### 方式二：从源码编译

```bash
cd go/
make build
```

### 配置

```bash
cp ../.env.example .env
# 编辑 .env，必须配置：
#   ZILLIZ_URI, ZILLIZ_TOKEN
#   EMBEDDING_PROVIDER=remote
#   EMBEDDING_API_BASE, EMBEDDING_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIM
```

### 测试

```bash
./vector-memory --test
```

## CLI 用法

```bash
# 写入一条记忆
./vector-memory --save "用户喜欢用 Go，讨厌复杂依赖"

# 语义搜索
./vector-memory --search "用户有什么编程习惯"

# 从 MEMORY.md 迁移记忆
./vector-memory --migrate /path/to/MEMORY.md

# 查看记忆总条数
./vector-memory --count
```

## 集成到 OpenClaw

```bash
./install.sh ~/workspace/openclaw
```

安装脚本会自动：
1. 复制二进制到目标目录
2. 交互式配置 `.env`
3. 在 `AGENTS.md` 中注入记忆工具指令

## Rerank 配置

与 Python 版完全一致，通过 `.env` 中的 `RERANK_*` 参数控制。详见 [主 README](../README.md) 中的参数表。

## 交叉编译

一键编译全平台：

```bash
make release
```

产物：

| 文件 | 平台 |
|------|------|
| `vector-memory-linux-amd64` | Linux x86_64 |
| `vector-memory-linux-arm64` | Linux ARM64 |
| `vector-memory-darwin-amd64` | macOS Intel |
| `vector-memory-darwin-arm64` | macOS Apple Silicon |
| `vector-memory-windows-amd64.exe` | Windows x86_64 |

## 项目结构

```
go/
├── cmd/vector-memory/main.go     # CLI 入口
├── internal/
│   ├── config/config.go          # .env 解析 + 配置结构
│   ├── embedder/embedder.go      # 远程 Embedding API 客户端
│   ├── rerank/rerank.go          # 重排策略 + Reranker 适配器
│   ├── store/store.go            # 核心存储层
│   ├── zilliz/client.go          # Zilliz Cloud REST 客户端
│   └── migrate/migrate.go        # Markdown 迁移
├── install.sh                    # 一键安装脚本
├── Makefile                      # 构建/发布
└── go.mod                        # 零第三方依赖
```
