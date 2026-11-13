#!/bin/bash
cd "$(dirname "$0")"

echo "========================================================"
echo "  🌿 KHỞI ĐỘNG GOOGLE PHOTOS ✕ EAGLE AI STUDIO (macOS)"
echo "========================================================"
echo ""

if curl -fsS http://127.0.0.1:8899/api/state >/dev/null 2>&1; then
    echo "✅ Hệ thống đang chạy, đang mở Dashboard trên trình duyệt..."
    open "http://127.0.0.1:8899"
    exit 0
fi

echo "📦 Đang kiểm tra thư viện Python..."
python3 -c 'import mcp,uvicorn,PIL,requests,cv2,jsonschema' 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Đang cài đặt thư viện phụ thuộc lần đầu (có thể mất 1-2 phút)..."
    python3 -m pip install -r requirements-vision.txt --break-system-packages 2>/dev/null || python3 -m pip install -r requirements-vision.txt
fi

echo "🚀 Đang mở giao diện macOS Dashboard..."
open "http://127.0.0.1:8899"

echo "🖥️ Dịch vụ đang chạy tại cổng 8899 (Nhấn Ctrl+C để dừng)..."
python3 server.py
