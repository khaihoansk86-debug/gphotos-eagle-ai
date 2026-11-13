"""Compatibility for old stdio configurations."""
import runpy
import sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
if __name__=='__main__':
    runpy.run_path(str(root/'mcp_bridge.py'),run_name='__main__')
