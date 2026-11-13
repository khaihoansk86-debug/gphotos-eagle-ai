@echo off
chcp 65001 > nul
title Đăng Nhập Google Photos - Profile Riêng Biệt

cd /d "%~dp0"
set "PROFILE_DIR=%~dp0browser_profile"

if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"

echo ========================================================
echo   🌐 MỞ TRÌNH DUYỆT RIÊNG CHO GOOGLE PHOTOS
echo   Profile lưu tại: %PROFILE_DIR%
echo   (Đăng nhập 1 lần, lưu vĩnh viễn, copy đi đâu cũng được)
echo ========================================================
echo.

set "CHROME_BIN="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_BIN=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_BIN if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_BIN=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_BIN if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_BIN=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_BIN if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "CHROME_BIN=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"

if not defined CHROME_BIN (
    echo [X] Không tìm thấy Chrome hoặc Edge trên máy của bạn.
    pause
    exit /b 1
)

start "" "%CHROME_BIN%" --user-data-dir="%PROFILE_DIR%" --new-window "https://photos.google.com"
echo [OK] Đã mở cửa sổ trình duyệt độc lập!
echo Hãy đăng nhập tài khoản Google Photos của bạn trên cửa sổ vừa mở.
timeout /t 3 > nul
