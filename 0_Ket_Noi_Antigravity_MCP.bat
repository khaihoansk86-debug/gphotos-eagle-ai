@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================================
echo   KET NOI ANTIGRAVITY (ANTI) - PHOTOS EAGLE MCP GATEWAY (WIN)
echo ================================================================

if exist "setup_antigravity_mcp.py" (
    python setup_antigravity_mcp.py
) else (
    python -c "import json; from pathlib import Path; h=Path.home(); [ (p.parent.mkdir(parents=True,exist_ok=True), d:=json.loads(p.read_text('utf-8')) if p.exists() else {}, d.setdefault('mcpServers',{}) .__setitem__('gphotos-content-vision',{'url':'http://127.0.0.1:8898/mcp'}), p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n','utf-8'), print('[OK]',p)) for p in [h/'.gemini/antigravity/mcp_config.json', h/'.gemini/config/mcp_config.json'] ]"
)

if exist "http_service.py" (
    powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8898/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
    if errorlevel 1 (
        echo -^> Dang khoi dong nen MCP Gateway (8898^) ^& Dashboard (8899^)...
        start "" /B pythonw http_service.py 2>nul || start "" /MIN python http_service.py
        timeout /t 2 /nobreak >nul
    )
    start "" "http://127.0.0.1:8899/"
)

echo.
echo HOAN TAT! Ban hay mo hoac reload Antigravity de AI nhan du 47 Tools MCP.
pause
