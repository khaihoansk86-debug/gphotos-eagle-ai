@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Khởi Động Khải Hoàn Skincare Dashboard

echo ========================================================
echo   🌿 KHỞI ĐỘNG GOOGLE PHOTOS ✕ EAGLE AI STUDIO
echo ========================================================
echo.

set "APP_PY=python"
if exist "%LocalAppData%\Python\bin\python.exe" set "APP_PY=%LocalAppData%\Python\bin\python.exe"

"%APP_PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8899/api/state',timeout=2)" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Hệ thống đang chạy, đang mở Dashboard trên trình duyệt...
    start "" http://127.0.0.1:8899
    exit /b 0
)

echo [1/2] Đang kiểm tra thư viện Python...
"%APP_PY%" -c "import mcp,uvicorn,PIL,requests,cv2,jsonschema" >nul 2>&1
if %errorlevel% neq 0 (
    echo Đang cài đặt thư viện phụ thuộc lần đầu...
    "%APP_PY%" -m pip install -r requirements-vision.txt
)

echo [2/2] Đang mở Dashboard tại http://127.0.0.1:8899 ...
start "" http://127.0.0.1:8899

"%APP_PY%" server.py
pause
