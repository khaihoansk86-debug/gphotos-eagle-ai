@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Cập Nhật GPhotos Eagle AI

echo ========================================================
echo   🔄 ĐANG KIỂM TRA VÀ CẬP NHẬT PHIÊN BẢN MỚI TỪ GIT
echo ========================================================
echo.

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Máy tính chưa cài đặt Git!
    echo Vui lòng tải Git tại: https://git-scm.com/
    pause
    exit /b 1
)

echo [1/2] Đang tải mã nguồn mới nhất về...
git pull
if %errorlevel% neq 0 (
    echo.
    echo ⚠️ Đang thử lại với nhánh main...
    git pull origin main
)

echo.
echo [2/2] Đang kiểm tra và cập nhật các thư viện phụ thuộc (Dependencies)...
set "APP_PY=python"
if exist "%LocalAppData%\Python\bin\python.exe" set "APP_PY=%LocalAppData%\Python\bin\python.exe"
"%APP_PY%" -m pip install -r requirements-vision.txt --quiet

echo.
echo ========================================================
echo   ✅ CẬP NHẬT HOÀN TẤT! HỆ THỐNG ĐÃ Ở PHIÊN BẢN MỚI NHẤT
echo ========================================================
echo Bạn có thể khởi động lại tool bằng cách chạy run_windows.bat
echo.
pause
