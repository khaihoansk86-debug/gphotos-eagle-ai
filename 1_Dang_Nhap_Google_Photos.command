#!/bin/bash
# ========================================================
#   🌐 MỞ TRÌNH DUYỆT RIÊNG CHO GOOGLE PHOTOS (macOS)
# ========================================================

cd "$(dirname "$0")"
PROFILE_DIR="$(pwd)/browser_profile"
mkdir -p "$PROFILE_DIR"

echo "========================================================"
echo "  🌐 MỞ TRÌNH DUYỆT RIÊNG CHO GOOGLE PHOTOS (macOS)"
echo "  Profile lưu tại: $PROFILE_DIR"
echo "========================================================"

# Use open -na to guarantee a completely new, isolated Chrome process on Mac!
open -na "Google Chrome" --args --user-data-dir="$PROFILE_DIR" --new-window "https://photos.google.com"

echo "Đã mở cửa sổ Google Photos với profile độc lập!"
sleep 2
