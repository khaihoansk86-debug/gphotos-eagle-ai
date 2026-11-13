@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "APP_PY=python"
if exist "%LocalAppData%\Python\bin\python.exe" set "APP_PY=%LocalAppData%\Python\bin\python.exe"
"%APP_PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8899/health',timeout=2)" >nul 2>&1
if %errorlevel% equ 0 (
 start "" http://127.0.0.1:8899
 exit /b 0
)
"%APP_PY%" -c "import mcp,uvicorn,PIL,requests,cv2,jsonschema" >nul 2>&1
if %errorlevel% neq 0 "%APP_PY%" -m pip install -r requirements-vision.txt
start "" http://127.0.0.1:8899
"%APP_PY%" server.py
pause
