#!/bin/bash
cd "$(dirname "$0")"

echo "========================================================"
echo "  🔄 ĐANG KIỂM TRA VÀ CẬP NHẬT PHIÊN BẢN MỚI TỪ GIT"
echo "========================================================"
echo ""

if ! command -v git &> /dev/null; then
    echo "[X] Máy tính chưa cài đặt Git!"
    read -p "Nhấn phím bất kỳ để thoát..."
    exit 1
fi

echo "[1/2] Đang tải mã nguồn mới nhất..."
git pull || git pull origin master

echo ""
echo "[2/2] Đang kiểm tra thư viện Python..."
python3 -m pip install -r requirements-vision.txt --quiet

echo ""
echo "========================================================"
echo "  ✅ CẬP NHẬT HOÀN TẤT! HỆ THỐNG ĐÃ Ở PHIÊN BẢN MỚI NHẤT"
echo "========================================================"
echo "Bạn có thể khởi động lại tool bằng run_mac.command"
read -p "Nhấn Enter để hoàn tất..."
