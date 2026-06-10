#!/bin/bash
# 妮可桌面宠物 — 一键启动/关闭
ROOT="$(cd "$(dirname "$0")" && pwd)"

# 先杀干净旧进程
echo " 清理旧进程..."
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null
pkill -f "python3.*main.py" 2>/dev/null
sleep 2

cleanup() {
    echo " 关闭中..."
    lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null
    exit 0
}
trap cleanup INT TERM

# 启动后端
echo " 启动后端..."
(cd "$ROOT" && python3 server/main.py &>/tmp/nicole_server.log) &
sleep 4

# 启动前端 (QT_MAC_DISABLE=1 防止 Dock 弹图标)
echo " 启动前端..."
(cd "$ROOT/frontend" && QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM=1 python3 main.py &>/tmp/nicole_frontend.log) &
FRONTEND_PID=$!

echo " 妮可就绪！Ctrl+C 关闭"
wait $FRONTEND_PID 2>/dev/null
cleanup
