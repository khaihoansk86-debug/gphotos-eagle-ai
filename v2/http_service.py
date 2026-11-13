"""Compatibility for an existing startup shortcut; the app lives at repo root."""
import runpy
import sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
if __name__=='__main__':
    runpy.run_path(str(root/'http_service.py'),run_name='__main__')
