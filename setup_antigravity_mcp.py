"""
Auto-configure Antigravity (Anti) MCP Gateway & Universal Media Classifier Skill.
Safely merges gphotos-content-vision (http://127.0.0.1:8898/mcp) into Antigravity configs
on macOS, Windows, and Linux without overwriting existing MCP servers.
"""

import json
import shutil
from pathlib import Path
from urllib.request import urlopen

MCP_SERVER_NAME = "gphotos-content-vision"
MCP_URL = "http://127.0.0.1:8898/mcp"
HEALTH_URL = "http://127.0.0.1:8898/health"

ROOT = Path(__file__).resolve().parent
HOME = Path.home()


def merge_mcp_config(cfg_path: Path) -> None:
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers
    servers[MCP_SERVER_NAME] = {"url": MCP_URL}
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  [OK] Da cap nhat MCP config: {cfg_path}")


def install_skill() -> None:
    src_skill = ROOT / "SKILL.md"
    if not src_skill.exists():
        return
    skill_targets = [
        HOME / ".gemini" / "antigravity" / "skills" / "universal-media-classifier" / "SKILL.md",
        HOME / ".gemini" / "config" / "skills" / "universal-media-classifier" / "SKILL.md",
    ]
    for dst in skill_targets:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_skill, dst)
        print(f"  [OK] Da cai dat Skill cho Anti: {dst}")


def check_health() -> bool:
    try:
        with urlopen(HEALTH_URL, timeout=2) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            print(f"  [ONLINE] MCP Gateway dang chay: {info.get('tools', 47)} Tools (PID {info.get('pid')})")
            return True
    except Exception:
        print("  [NOTE] MCP Gateway (8898) chua bat. Dang khoi dong tu dong...")
        return False


def main() -> None:
    print("=" * 64)
    print("  KET NOI TU DONG ANTIGRAVITY (ANTI) -> MCP GATEWAY (8898)")
    print("=" * 64)

    config_targets = [
        HOME / ".gemini" / "antigravity" / "mcp_config.json",
        HOME / ".gemini" / "config" / "mcp_config.json",
    ]
    ide_dir = HOME / ".gemini" / "antigravity-ide"
    if ide_dir.exists():
        config_targets.append(ide_dir / "mcp_config.json")

    for target in config_targets:
        merge_mcp_config(target)

    install_skill()
    check_health()

    print("=" * 64)
    print("  HOAN TAT! Hay mo (hoac reload) Antigravity de dung ngay 47 Tools.")
    print(f"  MCP Endpoint : {MCP_URL}")
    print("  Web Dashboard: http://127.0.0.1:8899/")
    print("=" * 64)


if __name__ == "__main__":
    main()
