#!/usr/bin/env bash

# 安装 openclaw-vector-memory (Go 版) 到指定的 OpenClaw 目录
# 用法: ./install.sh /path/to/openclaw

set -e

if [ -z "$1" ]; then
    echo "❌ 错误: 请指定 OpenClaw 项目目录的路径"
    echo "用法: ./install.sh /path/to/openclaw"
    exit 1
fi

TARGET_DIR="$1"

if [ ! -d "$TARGET_DIR" ]; then
    echo "❌ 错误: 目标目录 $TARGET_DIR 不存在"
    exit 1
fi

echo "🚀 开始安装 openclaw-vector-memory (Go 版) 到 $TARGET_DIR..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BIN_NAME="vector-memory"

# ── 1. 编译或复制或下载二进制 ──────────────────────────────────────

# 获取系统信息
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
    x86_64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
esac
ASSET_NAME="vector-memory-${OS}-${ARCH}"

# 检查是否有预编译的二进制 (本地开发)
if [ -f "$SCRIPT_DIR/$BIN_NAME" ]; then
    echo "-> 复制本地预编译二进制..."
    cp "$SCRIPT_DIR/$BIN_NAME" "$TARGET_DIR/$BIN_NAME"
# 有 Go 环境则编译 (源码环境)
elif command -v go &> /dev/null && [ -d "$SCRIPT_DIR/cmd" ]; then
    echo "-> 从源码编译..."
    cd "$SCRIPT_DIR"
    go build -o "$TARGET_DIR/$BIN_NAME" ./cmd/vector-memory/
# 从 GitHub Release 下载
else
    echo "-> 正在从 GitHub Releases 下载预编译二进制 ($ASSET_NAME)..."
    DOWNLOAD_URL="https://github.com/donglua/openclaw-vector-memory/releases/latest/download/$ASSET_NAME"
    
    if command -v curl &> /dev/null; then
        curl -L -o "$TARGET_DIR/$BIN_NAME" "$DOWNLOAD_URL"
    elif command -v wget &> /dev/null; then
        wget -O "$TARGET_DIR/$BIN_NAME" "$DOWNLOAD_URL"
    else
        echo "❌ 错误: 找不到 curl 或 wget 工具，无法下载。"
        exit 1
    fi
    
    # 验证文件是否下载成功（而不是 404 页面）
    if [ ! -s "$TARGET_DIR/$BIN_NAME" ] || head -n 1 "$TARGET_DIR/$BIN_NAME" | grep -q 'Not Found'; then
        echo "❌ 错误: 下载失败，可能是平台不支持 ($ASSET_NAME)。请参阅 README 手动下载或编译。"
        rm -f "$TARGET_DIR/$BIN_NAME"
        exit 1
    fi
fi

chmod +x "$TARGET_DIR/$BIN_NAME"
echo "✅ 二进制已安装到 $TARGET_DIR/$BIN_NAME"

# ── 2. 配置 .env ─────────────────────────────────────────────

echo "-> 配置 .env 环境 (交互式)..."
ENV_FILE="$TARGET_DIR/.env"

escape_sed_value() {
    printf '%s' "$1" | sed -e 's/[\\\/&]/\\&/g'
}

set_env_var() {
    local key="$1"
    local value="$2"
    local escaped
    escaped=$(escape_sed_value "$value")

    if grep -qE "^[#[:space:]]*${key}=" "$ENV_FILE"; then
        sed -i.bak -E "s|^[#[:space:]]*${key}=.*|${key}=${escaped}|" "$ENV_FILE"
    else
        printf '%s\n' "${key}=${value}" >> "$ENV_FILE"
    fi
}

# 如果没有 .env，从模板创建
if [ ! -f "$ENV_FILE" ]; then
    cp "$SCRIPT_DIR/../.env.example" "$ENV_FILE" 2>/dev/null || true
    echo "✅ 创建了新的 .env 文件"
fi

# 交互式填入
if grep -q "your-cluster-id" "$ENV_FILE" 2>/dev/null || grep -q "your_api_key_here" "$ENV_FILE" 2>/dev/null || [ ! -f "$ENV_FILE" ]; then
    # 确保 .env 存在
    touch "$ENV_FILE"
    
    echo "💡 Go 版仅支持远程 Embedding API（无需 Python/PyTorch），请填入以下配置："
    echo ""

    read -p "Zilliz URI (如 https://in03-xxxx...): " in_uri
    read -p "Zilliz Token (如 user:password): " in_token
    read -p "远程 API Base URL [默认 https://api.siliconflow.cn/v1]: " in_api_base
    in_api_base=${in_api_base:-https://api.siliconflow.cn/v1}
    read -p "远程 API Key: " in_api_key
    read -p "模型名称 [默认 Qwen/Qwen3-Embedding-8B]: " in_model
    in_model=${in_model:-Qwen/Qwen3-Embedding-8B}
    read -p "向量维度 [默认 4096]: " in_dim
    in_dim=${in_dim:-4096}

    [ -n "$in_uri" ]      && set_env_var "ZILLIZ_URI" "$in_uri"
    [ -n "$in_token" ]    && set_env_var "ZILLIZ_TOKEN" "$in_token"
    set_env_var "EMBEDDING_PROVIDER" "remote"
    [ -n "$in_api_base" ] && set_env_var "EMBEDDING_API_BASE" "$in_api_base"
    [ -n "$in_api_key" ]  && set_env_var "EMBEDDING_API_KEY" "$in_api_key"
    [ -n "$in_model" ]    && set_env_var "EMBEDDING_MODEL" "$in_model"
    [ -n "$in_dim" ]      && set_env_var "EMBEDDING_DIM" "$in_dim"

    rm -f "$ENV_FILE.bak"
    echo "✅ 环境变量已配置到 $ENV_FILE"
else
    echo "⚠️ 目标 .env 似乎已包含有效配置，跳过交互式填入。"
fi

# ── 3. 注入 Agent 指令到 AGENTS.md ──────────────────────────

echo "-> 正在注入 Agent 记忆指令..."
AGENTS_FILE="$TARGET_DIR/AGENTS.md"
if [ -f "$AGENTS_FILE" ]; then
    if grep -q "长期向量记忆库" "$AGENTS_FILE"; then
        echo "⚠️ AGENTS.md 似乎已包含向量记忆工具的指令，跳过注入。"
    else
        cat << 'EOF' >> "$AGENTS_FILE"

---

# 🧠 长期向量记忆库 (自动注入)
**核心指令**：不要直接读取或写入传统的 `MEMORY.md` 文件。对于用户的偏好、长期记忆、以及背景上下文，请使用以下向量搜索工具：
1. **检索记忆**：当你需要回忆关于用户的信息时，使用终端执行：
   `./vector-memory --search "你要检索的关键语义"`
2. **保存记忆**：当用户告知你全新的偏好或长期有效的事实，使用终端执行：
   `./vector-memory --save "清晰且完整的记忆内容"`
EOF
        echo "✅ 成功将向量记忆指令注入到 AGENTS.md！"
    fi
else
    echo "⚠️ 目标目录未找到 AGENTS.md，跳过指令注入。"
fi

echo ""
echo "🎉 安装完成！无需 Python、无需 pip、无需 venv"
echo "   测试运行: cd $TARGET_DIR && ./vector-memory --test"
