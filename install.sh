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

# 1. 复制 memory 文件夹
echo "-> 复制 memory 模块..."
cp -r memory "$TARGET_DIR/"
if [ $? -ne 0 ]; then
    echo "❌ 复制文件失败"
    exit 1
fi

# 2. 追加或创建 .env 文件
echo "-> 配置 .env 环境..."
if [ ! -f "$TARGET_DIR/.env" ]; then
    cp .env.example "$TARGET_DIR/.env"
    echo "✅ 创建了新的 .env 文件"
else
    # 检查是否已经包含了 ZILLIZ_URI
    if grep -q "ZILLIZ_URI" "$TARGET_DIR/.env"; then
        echo "⚠️ 目标 .env 似乎已包含向量数据库配置，跳过追加。"
    else
        echo "" >> "$TARGET_DIR/.env"
        cat .env.example >> "$TARGET_DIR/.env"
        echo "✅ Zilliz 与 Provider 配置已追加到现有的 .env 中"
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
    echo "✅ 依赖已追加到 requirements.txt，请进入目录执行 pip install -r requirements.txt"
else
    cp requirements.txt "$TARGET_DIR/"
    echo "✅ 创建了 requirements.txt"
fi

echo "🎉 安装完成！"
echo "👉 下一步："
echo "1. cd $TARGET_DIR"
echo "2. 编辑 .env 配置你的 API 密钥和 Provider"
echo "3. pip install -r requirements.txt"
echo "4. 在代码中: from memory import MemoryStore"
