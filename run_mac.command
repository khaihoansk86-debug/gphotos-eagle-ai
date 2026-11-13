#!/bin/bash
cd "$(dirname "$0")"
if curl -fsS http://127.0.0.1:8899/health >/dev/null 2>&1; then
 open http://127.0.0.1:8899
 exit 0
fi
python3 -c 'import mcp,uvicorn,PIL,requests,cv2,jsonschema' || python3 -m pip install -r requirements-vision.txt
open http://127.0.0.1:8899
python3 server.py
