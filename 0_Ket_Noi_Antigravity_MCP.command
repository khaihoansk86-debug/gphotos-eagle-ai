#!/bin/bash
# 1-Click: Tu dong ket noi Antigravity (Anti) vao MCP Gateway (8898) tren macOS
set -e
cd "$(dirname "$0")"

echo "================================================================"
echo "  KET NOI ANTIGRAVITY (ANTI) -> PHOTOS EAGLE MCP GATEWAY (macOS)"
echo "================================================================"

if [ -f "setup_antigravity_mcp.py" ]; then
  python3 setup_antigravity_mcp.py
else
  python3 - <<'PY'
import json
from pathlib import Path
home = Path.home()
for p in [
    home / ".gemini" / "antigravity" / "mcp_config.json",
    home / ".gemini" / "config" / "mcp_config.json",
]:
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("mcpServers", {})["gphotos-content-vision"] = {"url": "http://127.0.0.1:8898/mcp"}
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[OK] Da ket noi MCP trong:", p)
PY
fi

# Tu dong bat MCP + Dashboard server neu chua chay (khi chay trong thu muc repo)
if [ -f "http_service.py" ]; then
  if ! curl -s http://127.0.0.1:8898/health >/dev/null 2>&1; then
    echo "-> Dang khoi dong nen MCP Gateway (8898) & Dashboard (8899)..."
    nohup python3 http_service.py >/tmp/gphotos_eagle_mcp.log 2>&1 &
    sleep 2
  fi
  open "http://127.0.0.1:8899/" >/dev/null 2>&1 || true
fi

echo ""
echo "HOAN TAT! Ban hay mo/reload Antigravity de AI nhan du 47 Tools MCP."
read -p "Nhan Enter de dong cua so nay..."
