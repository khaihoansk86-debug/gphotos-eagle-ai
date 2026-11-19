import os
import re
import json
from pathlib import Path

LIBRARY_PATH = Path(r"D:\test.library")
IMAGES_DIR = LIBRARY_PATH / "images"
CACHE_FILE = Path(os.path.expandvars(r"%APPDATA%\Eagle\library-caches\5d59398c.txt"))

def sanitize(s: str) -> str:
    # Remove illegal windows characters: \ / : * ? " < > |
    s = re.sub(r'[:*?"<>|/\\]', '', s)
    return s.strip()

def run():
    info_dirs = list(IMAGES_DIR.glob("*.info"))
    print(f"Total folders to check: {len(info_dirs)}")

    fixed_count = 0
    already_ok = 0
    no_media = 0
    cache_items = []

    for d in info_dirs:
        mf = d / "metadata.json"
        if not mf.exists():
            continue
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue

        raw_name = m.get("name", "")
        ext = m.get("ext", "jpg")

        # Clean name so it has NO illegal windows filename characters
        safe_name = sanitize(raw_name)
        if not safe_name:
            safe_name = d.stem

        # Find existing media files in directory
        media_files = [
            f for f in d.iterdir()
            if f.name != "metadata.json" and not f.name.endswith("_thumbnail.png")
        ]

        if not media_files:
            no_media += 1
            cache_items.append(m)
            continue

        current_file = media_files[0]
        expected_file = d / f"{safe_name}.{ext}"

        # If current file does not match expected_file, rename it!
        if current_file != expected_file:
            try:
                # If target already exists, don't overwrite
                if expected_file.exists() and expected_file != current_file:
                    current_file.unlink()
                else:
                    current_file.rename(expected_file)
                fixed_count += 1
            except Exception as e:
                # If renaming fails (e.g. filename too long), fallback to current_file.stem
                safe_name = sanitize(current_file.stem)
                expected_file = d / f"{safe_name}.{ext}"
                try:
                    if current_file != expected_file:
                        current_file.rename(expected_file)
                    fixed_count += 1
                except Exception as e2:
                    print(f"Error renaming in {d.name}: {e2}")

        # Update metadata.json to ensure name exactly matches the file on disk!
        m["name"] = expected_file.stem
        m["ext"] = expected_file.suffix.lstrip(".").lower()
        mf.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        cache_items.append(m)
        if current_file == expected_file:
            already_ok += 1

    # Update cache file
    if CACHE_FILE.parent.exists():
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for item in cache_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Done! Fixed {fixed_count} files. Already OK: {already_ok}. No media: {no_media}.")
    print(f"Total items in cache: {len(cache_items)}")

if __name__ == "__main__":
    run()
