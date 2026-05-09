#!/bin/bash

# 以调试模式启动一个独立的 Google Chrome 实例（与你日常使用的 Chrome 完全隔离）
#
# 关键点：
# - 用 Chrome 二进制 + nohup & 后台启动，绕过 macOS `open -a` 在 Chrome
#   已经运行时把参数吞掉的劫持问题
# - 用独立 user-data-dir，与日常 Chrome 的 profile 完全分离，互不影响
# - 即使你已经开着普通 Chrome，这个脚本也会再开一个独立窗口

PORT=9222
DATA_DIR="$HOME/.social_uploader/chrome_profiles/default"
CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [ ! -x "$CHROME_BIN" ]; then
    echo "错误：找不到 Chrome 可执行文件：$CHROME_BIN"
    echo "请确认 Google Chrome 已安装在 /Applications/ 目录下"
    exit 1
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Chrome 调试模式已在运行 (端口 $PORT)，无需重复启动"
    exit 0
fi

mkdir -p "$DATA_DIR"

echo "正在以调试模式启动 Google Chrome (端口 $PORT)..."
echo "  使用独立 user-data-dir：$DATA_DIR"
echo "  你日常使用的 Chrome 不会受影响"

nohup "$CHROME_BIN" \
    --remote-debugging-port="$PORT" \
    --user-data-dir="$DATA_DIR" \
    --disable-blink-features=AutomationControlled \
    --remote-allow-origins="*" \
    --no-first-run \
    --no-default-browser-check \
    --restore-last-session \
    >/dev/null 2>&1 &

CHROME_PID=$!
disown "$CHROME_PID" 2>/dev/null || true

# 轮询等待端口就绪（最多 8 秒）
for i in 1 2 3 4 5 6 7 8; do
    if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "✅ 启动成功！调试端口 $PORT 已就绪 (Chrome PID=$CHROME_PID)"
        echo ""
        echo "下一步："
        echo "  1. 在新打开的 Chrome 窗口里登录目标平台（YouTube Studio / TikTok Studio / Instagram）"
        echo "  2. 登录完成后即可运行采集或上传命令"
        echo ""
        echo "数据目录：$DATA_DIR （登录状态保存在这里，下次自动恢复）"
        exit 0
    fi
    sleep 1
done

echo "⚠️  Chrome 已启动 (PID=$CHROME_PID)，但端口 $PORT 8 秒内尚未就绪"
echo "   请稍等几秒后用以下命令重新检查："
echo "     lsof -nP -iTCP:$PORT -sTCP:LISTEN"
exit 1
