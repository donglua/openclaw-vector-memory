#!/usr/bin/env bash

# 安装 openclaw-vector-memory 到指定的 OpenClaw 目錄

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

echo "🚀 开始安装 openclaw-vector-memory 到 $TARGET_DIR..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 1. 复制 memory 文件夹和执行入口
echo "-> 复制核心模块..."
cp -r "$SCRIPT_DIR/memory" "$TARGET_DIR/"
cp "$SCRIPT_DIR/main.py" "$TARGET_DIR/vector_memory.py"
if [ $? -ne 0 ]; then
    echo "❌ 复制文件失败"
    exit 1
fi

# 2. 追加或创建 .env 文件
echo "-> 配置 .env 环境 (交互式)..."
ENV_FILE="$TARGET_DIR/.env"

# 如果没有 .env 文件，先从模板创建
if [ ! -f "$ENV_FILE" ]; then
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    echo "✅ 创建了新的 .env 文件"
fi

# 检查是否保留了模板里的默认标记
if grep -q "your-cluster-id" "$ENV_FILE" || grep -q "your_api_key_here" "$ENV_FILE"; then
    echo "💡 发现环境变量未配置，现在进行交互式填入 (按回车跳过并保留默认模板)："

    read -p "Zilliz URI (如 https://in03-xxxx...): " in_uri
    read -p "Zilliz Token (如 user:password): " in_token

    echo "Embedding 提供商可选项: local(本地), remote(远程硅基/OpenAI等)"
    read -p "Embedding Provider [默认 local]: " in_provider

    if [ "$in_provider" = "remote" ]; then
        read -p "远程 API Base URL [如 https://api.siliconflow.cn/v1]: " in_api_base
        read -p "远程 API Key: " in_api_key
        read -p "模型名称 [默认 BAAI/bge-m3]: " in_model
        read -p "向量维度 [默认 1024]: " in_dim
    fi

    # 替换或追加配置到 .env
    [ -n "$in_uri" ] && sed -i.bak "s|^ZILLIZ_URI=.*|ZILLIZ_URI=$in_uri|" "$ENV_FILE"
    [ -n "$in_token" ] && sed -i.bak "s|^ZILLIZ_TOKEN=.*|ZILLIZ_TOKEN=$in_token|" "$ENV_FILE"
    [ -n "$in_provider" ] && sed -i.bak "s|^EMBEDDING_PROVIDER=.*|EMBEDDING_PROVIDER=$in_provider|" "$ENV_FILE"

    if [ "$in_provider" = "remote" ]; then
        # 确保包含远程 API 配置变量
        for var in EMBEDDING_API_BASE EMBEDDING_API_KEY EMBEDDING_MODEL EMBEDDING_DIM; do
            if ! grep -q "^$var=" "$ENV_FILE" && ! grep -q "^# $var=" "$ENV_FILE"; then
                echo "$var=" >> "$ENV_FILE"
            fi
        done
        [ -n "$in_api_base" ] && sed -i.bak "s|^#* *EMBEDDING_API_BASE=.*|EMBEDDING_API_BASE=$in_api_base|" "$ENV_FILE"
        [ -n "$in_api_key" ]  && sed -i.bak "s|^#* *EMBEDDING_API_KEY=.*|EMBEDDING_API_KEY=$in_api_key|" "$ENV_FILE"
        [ -n "$in_model" ]    && sed -i.bak "s|^#* *EMBEDDING_MODEL=.*|EMBEDDING_MODEL=$in_model|" "$ENV_FILE"
        [ -n "$in_dim" ]      && sed -i.bak "s|^#* *EMBEDDING_DIM=.*|EMBEDDING_DIM=$in_dim|" "$ENV_FILE"
    fi
    rm -f "$ENV_FILE.bak"
    echo "✅ 环境变量已自动配置到 $ENV_FILE！"
else
    # 原本有 .env 且不是模板的默认，或者没写进去（从老版本追加）
    if ! grep -q "ZILLIZ_URI" "$ENV_FILE"; then
        echo "" >> "$ENV_FILE"
        cat "$SCRIPT_DIR/.env.example" >> "$ENV_FILE"
        echo "✅ Zilliz 与 Provider 配置已追加到现有的 .env 中，请手动完善里面未填的内容。"
    else
        echo "⚠️ 目标 .env 似乎已包含有效向量数据库配置，跳过交互式填入。"
    fi
fi

# 3. 追加依赖到 requirements.txt
echo "-> 追加依赖..."
if [ -f "$TARGET_DIR/requirements.txt" ]; then
    for dep in "FlagEmbedding" "pymilvus" "python-dotenv" "openai" "requests"; do
        if ! grep -q "$dep" "$TARGET_DIR/requirements.txt"; then
            echo "$dep" >> "$TARGET_DIR/requirements.txt"
        fi
    done
    echo "✅ 依赖已追加到 requirements.txt"
else
    cp "$SCRIPT_DIR/requirements.txt" "$TARGET_DIR/"
    echo "✅ 创建了 requirements.txt"
fi

# 4. 尝试自动安装依赖
echo "-> 正在自动安装依赖 (pip)..."
cd "$TARGET_DIR" || exit 1
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install --user -r requirements.txt --break-system-packages
elif command -v pip &> /dev/null; then
    pip install -r requirements.txt
else
    echo "⚠️ 找不到 pip 或 pip3，请手动跑: pip install -r requirements.txt"
fi

# 5. 自动修改 Agent 指令（AGENTS.md）以接入该工具
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
   `python3 vector_memory.py --search "你要检索的关键语义"`
2. **保存记忆**：当用户告知你全新的偏好或长期有效的事实，使用终端执行：
   `python3 vector_memory.py --save "清晰且完整的记忆内容"`
EOF
        echo "✅ 成功将向量记忆指令注入到 AGENTS.md！"
    fi
else
    echo "⚠️ 目标目录未找到 AGENTS.md，跳过指令注入。请手动将指令加入你的 Agent Prompt 中。"
fi

echo "🎉 安装与配置全部完成！"
