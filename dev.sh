#!/bin/bash
# 本地开发启动脚本
# MCP 在 Docker 中运行，Python 后端本地运行（支持热重载）

set -e

echo "=== 小红书 AI 运营平台 — 本地开发 ==="

# 确保 MCP 在 Docker 中运行
if ! docker compose ps mcp 2>/dev/null | grep -q "Up"; then
    echo "启动 MCP 容器…"
    docker compose up -d mcp
    sleep 2
fi

# 检查 MCP 状态
if curl -s http://localhost:18060/health | grep -q healthy; then
    echo "✅ MCP 服务就绪 (localhost:18060)"
else
    echo "❌ MCP 服务不可达"
    exit 1
fi

# 安装依赖（如需要）
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# 启动本地后端（热重载模式）
echo "✅ 启动本地后端 (localhost:8080)…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
