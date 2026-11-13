"""Bounded, read-only snapshot from the explicitly selected local browser profile."""
import json
import shutil
import subprocess
import time
from pathlib import Path


def read_profile(profile_path):
    node = shutil.which('node')
    if not node or not (Path(profile_path) / 'DevToolsActivePort').is_file():
        return {'status': 'bridge_required', 'checked_at': time.time()}
    try:
        run = subprocess.run([node, str(Path(__file__).with_name('photos_snapshot.js')), str(profile_path)],
                             capture_output=True, text=True, encoding='utf-8', timeout=12,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        data = json.loads(run.stdout)
        if not isinstance(data, dict):
            raise ValueError('Invalid snapshot')
        data['checked_at'] = time.time()
        return data
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'unavailable', 'checked_at': time.time()}
