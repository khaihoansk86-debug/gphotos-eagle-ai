"""
Real Google Photos Album Membership Scanner & Clean Eagle Rebuilder.
- Scans ALL real Google Photos albums via Chrome bridge (photos_scan_all_albums.js).
- Saves exact (album_id, album_title, media_key) relationships into SQLite `photos_album_members`.
- Rebuilds Eagle customer tags & folders cleanly (OVERWRITES wrong date-guessed tags, NEVER stacks).
- Preserves all valid functional classifications (Hero, Before-After, Treatment, Facility, Hook 3s, B-Roll, Archive).
- Creates customer sub-folders ONLY for real albums that actually have matched items (no empty ghost folders).
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

from reorganize_eagle_tree import (
    F_ROOT_PHOTO, F_PHOTO_HERO, F_PHOTO_BEFORE_AFTER, F_PHOTO_TREATMENT, F_PHOTO_FACILITY, F_PHOTO_CUSTOMERS,
    F_ROOT_VIDEO, F_VIDEO_HOOK, F_VIDEO_SPEECH, F_VIDEO_ASMR, F_VIDEO_BROLL, F_VIDEO_MUTE, F_VIDEO_CUSTOMERS,
)
from full_sync_eagle import F_PHOTO_ARCHIVE

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "v2" / "data" / "catalog.sqlite"
EAGLE_LIB = Path(r"D:\test.library")
IMAGES_DIR = EAGLE_LIB / "images"
PROFILE_ID = "2e3744dd5f5e4b9ea37a4e5b6f49b98c"

VALID_FUNCTIONAL_FOLDERS = {
    F_ROOT_PHOTO, F_PHOTO_HERO, F_PHOTO_BEFORE_AFTER, F_PHOTO_TREATMENT, F_PHOTO_FACILITY, F_PHOTO_ARCHIVE,
    F_ROOT_VIDEO, F_VIDEO_HOOK, F_VIDEO_SPEECH, F_VIDEO_ASMR, F_VIDEO_BROLL, F_VIDEO_MUTE,
}


def make_folder_id(prefix: str, seed: str) -> str:
    h = hashlib.md5(f"{prefix}:{seed}".encode("utf-8")).hexdigest().upper()
    return f"{prefix}_{h[:10]}"


def normalize_photo_key(url_or_key: str) -> str:
    if not url_or_key:
        return ""
    m = re.search(r"(/photo/[^/?#]+)", str(url_or_key))
    return m.group(1) if m else ""


def clean_tag_customer(title: str) -> str:
    # Keep readable Vietnamese customer name in tag without breaking spaces/symbols
    t = re.sub(r"\s+", " ", (title or "").strip())
    return f"Khách: {t}"


def init_album_members_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS photos_album_members (
            profile_id TEXT NOT NULL,
            album_id TEXT NOT NULL,
            album_title TEXT NOT NULL,
            media_key TEXT NOT NULL,
            photo_url TEXT NOT NULL,
            label TEXT DEFAULT '',
            updated REAL NOT NULL,
            PRIMARY KEY (profile_id, album_id, media_key)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_album_members_key ON photos_album_members(profile_id, media_key)")


def scan_all_real_albums(force_rescan: bool = False) -> Dict[str, List[Tuple[str, str]]]:
    """
    Scans all albums in `photos_albums` via Chrome bridge and returns:
      { media_key: [(album_id, album_title), ...] }
    """
    with sqlite3.connect(str(DB_FILE)) as db:
        db.row_factory = sqlite3.Row
        init_album_members_table(db)
        prof = db.execute("SELECT path FROM profiles WHERE id=?", (PROFILE_ID,)).fetchone()
        if not prof:
            raise RuntimeError(f"Profile not found: {PROFILE_ID}")
        profile_dir = prof["path"]

        albums = [
            dict(r)
            for r in db.execute(
                "SELECT id, title, album_url, item_count FROM photos_albums WHERE profile_id=? ORDER BY item_count DESC",
                (PROFILE_ID,),
            ).fetchall()
        ]

        already_scanned = {
            r["album_id"]
            for r in db.execute(
                "SELECT DISTINCT album_id FROM photos_album_members WHERE profile_id=?",
                (PROFILE_ID,),
            ).fetchall()
        }

    to_scan = albums if force_rescan else [a for a in albums if a["id"] not in already_scanned]
    print(f"📁 Tổng số Album thật trong SQLite: {len(albums)} | Cần quét: {len(to_scan)}", flush=True)

    if to_scan:
        node = shutil.which("node")
        script = str(BASE_DIR / "photos_scan_all_albums.js")
        proc = subprocess.Popen(
            [node, script, profile_dir],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
        proc.stdin.write(json.dumps({"albums": to_scan}))
        proc.stdin.close()

        now = time.time()
        with sqlite3.connect(str(DB_FILE)) as db:
            init_album_members_table(db)
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("event") == "album_done":
                        aid = ev["album_id"]
                        title = ev["title"]
                        items = ev.get("items", [])
                        if force_rescan:
                            db.execute(
                                "DELETE FROM photos_album_members WHERE profile_id=? AND album_id=?",
                                (PROFILE_ID, aid),
                            )
                        for it in items:
                            mk = normalize_photo_key(it.get("media_key") or it.get("photo_url"))
                            if not mk:
                                continue
                            db.execute(
                                """
                                INSERT OR REPLACE INTO photos_album_members
                                (profile_id, album_id, album_title, media_key, photo_url, label, updated)
                                VALUES (?,?,?,?,?,?,?)
                                """,
                                (PROFILE_ID, aid, title, mk, it.get("photo_url", ""), it.get("label", ""), now),
                            )
                        db.commit()
                        print(
                            f"  [{ev['idx']:2d}/{ev['total']}] {title}: tìm thấy {ev['found']}/{ev['expected']} mục thật",
                            flush=True,
                        )
                except Exception:
                    pass

        err = proc.stderr.read().strip()
        ret = proc.wait()
        if ret != 0 and err:
            raise RuntimeError(f"Lỗi quét album: {err}")

    # Load complete real mapping from SQLite
    mapping: Dict[str, List[Tuple[str, str]]] = {}
    with sqlite3.connect(str(DB_FILE)) as db:
        db.row_factory = sqlite3.Row
        for r in db.execute(
            "SELECT album_id, album_title, media_key FROM photos_album_members WHERE profile_id=?",
            (PROFILE_ID,),
        ).fetchall():
            mapping.setdefault(r["media_key"], []).append((r["album_id"], r["album_title"]))
    return mapping


def normalize_label_key(label: str) -> str:
    """Normalizes Google Photos second-precision timestamp+orientation label for 100% exact matching."""
    if not label:
        return ""
    s = re.sub(r'[:*?"<>|/\\]', '', str(label).strip())
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def load_real_album_lookup() -> Tuple[Dict[str, List[Tuple[str, str]]], Dict[str, List[Tuple[str, str]]]]:
    """
    Loads both media_key lookup and exact timestamp-label lookup from `photos_album_members`.
    """
    by_key: Dict[str, List[Tuple[str, str]]] = {}
    by_label: Dict[str, List[Tuple[str, str]]] = {}
    with sqlite3.connect(str(DB_FILE)) as db:
        db.row_factory = sqlite3.Row
        for r in db.execute(
            "SELECT album_id, album_title, media_key, label FROM photos_album_members WHERE profile_id=?",
            (PROFILE_ID,),
        ).fetchall():
            pair = (r["album_id"], r["album_title"])
            if r["media_key"]:
                lst = by_key.setdefault(r["media_key"], [])
                if pair not in lst:
                    lst.append(pair)
            lk = normalize_label_key(r["label"])
            if lk:
                lst2 = by_label.setdefault(lk, [])
                if pair not in lst2:
                    lst2.append(pair)
    return by_key, by_label


def rebuild_eagle_clean_with_real_albums(
    by_key: Dict[str, List[Tuple[str, str]]],
    by_label: Dict[str, List[Tuple[str, str]]],
) -> Dict[str, int]:
    """
    Cleans all wrong date-guessed customer tags & folders across D:\\test.library,
    preserves valid functional classifications, and builds customer sub-folders
    ONLY for real albums that have matched assets.
    """
    now_ms = int(time.time() * 1000)

    # First pass: inspect all Eagle items and count real album matches per branch (photo vs video)
    photo_album_counts: Dict[Tuple[str, str], int] = {}
    video_album_counts: Dict[Tuple[str, str], int] = {}

    info_dirs = list(IMAGES_DIR.glob("*.info"))
    print(f"🧹 Đang làm sạch tag sai & gắn lại đúng Album thật cho {len(info_dirs):,} mục trong Eagle...", flush=True)

    matched_items = 0
    unmatched_items = 0
    cleaned_wrong_tags = 0

    for d in info_dirs:
        mf = d / "metadata.json"
        if not mf.exists():
            continue
        try:
            meta = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue

        photo_key = normalize_photo_key(meta.get("url", ""))
        label_key = normalize_label_key(meta.get("name", ""))
        real_albums = list(by_key.get(photo_key, []))
        for pair in by_label.get(label_key, []):
            if pair not in real_albums:
                real_albums.append(pair)

        old_tags = meta.get("tags") or []
        old_folders = meta.get("folders") or []

        is_video = (
            F_ROOT_VIDEO in old_folders
            or (meta.get("name") or "").startswith("Video")
            or any("Video" in t or "Reels" in t or "Hook" in t for t in old_tags)
        )

        # 1. CLEAN TAGS: strip ALL old wrong date-guessed `Khách_*` / `Khách: *` tags, keep valid functional tags
        kept_tags = []
        for t in old_tags:
            if t.startswith("Khách_") or t.startswith("Khách:") or t.startswith("Khach_"):
                cleaned_wrong_tags += 1
                continue
            kept_tags.append(t)

        # 2. CLEAN FOLDERS: keep ONLY valid functional folders (drop ALL old wrong MP_* / MV_* customer folders)
        new_folders = [fid for fid in old_folders if fid in VALID_FUNCTIONAL_FOLDERS]
        if is_video:
            if F_ROOT_VIDEO not in new_folders:
                new_folders.insert(0, F_ROOT_VIDEO)
            # Ensure no photo folders leaked into video
            new_folders = [fid for fid in new_folders if fid in {F_ROOT_VIDEO, F_VIDEO_HOOK, F_VIDEO_SPEECH, F_VIDEO_ASMR, F_VIDEO_BROLL, F_VIDEO_MUTE}]
            if len(new_folders) == 1:
                new_folders.append(F_VIDEO_BROLL)
        else:
            if F_ROOT_PHOTO not in new_folders:
                new_folders.insert(0, F_ROOT_PHOTO)
            new_folders = [fid for fid in new_folders if fid in {F_ROOT_PHOTO, F_PHOTO_HERO, F_PHOTO_BEFORE_AFTER, F_PHOTO_TREATMENT, F_PHOTO_FACILITY, F_PHOTO_ARCHIVE}]
            if len(new_folders) == 1:
                new_folders.append(F_PHOTO_ARCHIVE)

        # 3. APPLY 100% REAL ALBUM TAGS & CUSTOMER FOLDERS
        if real_albums:
            matched_items += 1
            for aid, atitle in real_albums:
                kept_tags.append(clean_tag_customer(atitle))
                if is_video:
                    video_album_counts[(aid, atitle)] = video_album_counts.get((aid, atitle), 0) + 1
                    new_folders.append(make_folder_id("AV", aid))
                else:
                    photo_album_counts[(aid, atitle)] = photo_album_counts.get((aid, atitle), 0) + 1
                    new_folders.append(make_folder_id("AP", aid))
        else:
            unmatched_items += 1

        # Update annotation customer line cleanly (remove fake customer name)
        ann = meta.get("annotation") or ""
        real_names_str = ", ".join(atitle for _, atitle in real_albums) if real_albums else "Kho chung (chưa nằm trong album khách)"
        if "• Khách hàng:" in ann:
            ann = re.sub(r"• Khách hàng:.*", f"• Khách hàng (Album thật): {real_names_str}", ann)
        elif "• Khách hàng (Album thật):" in ann:
            ann = re.sub(r"• Khách hàng \(Album thật\):.*", f"• Khách hàng (Album thật): {real_names_str}", ann)

        meta["tags"] = list(dict.fromkeys(kept_tags))
        meta["folders"] = list(dict.fromkeys(new_folders))
        meta["annotation"] = ann
        meta["modificationTime"] = now_ms
        mf.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. REBUILD CLEAN 2-BRANCH TREE WITH ONLY NON-EMPTY REAL ALBUM FOLDERS
    photo_cust_children = []
    for (aid, atitle), cnt in sorted(photo_album_counts.items(), key=lambda x: x[1], reverse=True):
        photo_cust_children.append({
            "id": make_folder_id("AP", aid),
            "name": f"📁 {atitle} ({cnt})",
            "description": f"Ảnh thật từ Album Google Photos: {atitle}",
            "children": [],
            "modificationTime": now_ms,
            "tags": [clean_tag_customer(atitle)],
            "icon": "folder",
            "iconColor": "default",
        })

    video_cust_children = []
    for (aid, atitle), cnt in sorted(video_album_counts.items(), key=lambda x: x[1], reverse=True):
        video_cust_children.append({
            "id": make_folder_id("AV", aid),
            "name": f"🎬 {atitle} ({cnt})",
            "description": f"Video thật từ Album Google Photos: {atitle}",
            "children": [],
            "modificationTime": now_ms,
            "tags": [clean_tag_customer(atitle)],
            "icon": "folder",
            "iconColor": "default",
        })

    clean_tree = [
        {
            "id": F_ROOT_PHOTO,
            "name": "📸 1. KHO HÌNH ẢNH (Photo Studio)",
            "description": "100% ảnh tĩnh (đã chuẩn hóa theo Album thật)",
            "modificationTime": now_ms,
            "tags": ["Ảnh_Tĩnh"],
            "icon": "folder",
            "iconColor": "blue",
            "children": [
                {"id": F_PHOTO_HERO, "name": "⭐ 1.1 Ảnh 5 Sao Hero (Quảng Cáo & Bìa)", "description": "Ảnh sắc nét nhất mỗi phiên", "children": [], "modificationTime": now_ms, "tags": ["Chất_Lượng_5_Sao_Hero"], "icon": "folder", "iconColor": "yellow"},
                {"id": F_PHOTO_BEFORE_AFTER, "name": "🔄 1.2 Cặp Ảnh Trước & Sau (Before - After)", "description": "Ảnh đối chiếu trước & sau liệu trình", "children": [], "modificationTime": now_ms, "tags": ["Before_After"], "icon": "folder", "iconColor": "green"},
                {"id": F_PHOTO_TREATMENT, "name": "💆‍♀️ 1.3 Thao Tác KTV & Bác Sĩ", "description": "Quy trình thực hiện liệu trình", "children": [], "modificationTime": now_ms, "tags": ["Thao_Tác_KTV"], "icon": "folder", "iconColor": "purple"},
                {"id": F_PHOTO_FACILITY, "name": "🏥 1.4 Cơ Sở Vật Chất & Công Nghệ", "description": "Không gian & máy móc", "children": [], "modificationTime": now_ms, "tags": ["Cơ_Sở_Vật_Chất"], "icon": "folder", "iconColor": "orange"},
                {"id": F_PHOTO_CUSTOMERS, "name": f"👥 1.5 Hồ Sơ Khách Hàng Theo Album Thật ({len(photo_cust_children)} Album)", "description": "Khớp 100% theo Album thật trên Google Photos", "children": photo_cust_children, "modificationTime": now_ms, "tags": ["Hồ_Sơ_Khách_Hàng"], "icon": "folder", "iconColor": "aqua"},
                {"id": F_PHOTO_ARCHIVE, "name": "🗂️ 1.6 Ảnh Phụ & Lưu Trữ (Không Bỏ Sót)", "description": "Giữ nguyên 100% góc phụ trong chuỗi chụp", "children": [], "modificationTime": now_ms, "tags": ["Lưu_Trữ_Đầy_Đủ"], "icon": "folder", "iconColor": "default"},
            ],
        },
        {
            "id": F_ROOT_VIDEO,
            "name": "🎬 2. KHO VIDEO CLIPS (Video Reels & TikTok)",
            "description": "100% video clip dọc 9:16 (đã chuẩn hóa theo Album thật)",
            "modificationTime": now_ms,
            "tags": ["Video_Dọc_9:16"],
            "icon": "folder",
            "iconColor": "red",
            "children": [
                {"id": F_VIDEO_HOOK, "name": "🔥 2.1 Video Hook 3s Viral", "description": "Mở đầu giữ chân người xem", "children": [], "modificationTime": now_ms, "tags": ["Hook_3s_Viral"], "icon": "folder", "iconColor": "red"},
                {"id": F_VIDEO_SPEECH, "name": "🗣️ 2.2 Video Có Lời Thoại (Whisper AI)", "description": "Video có bác sĩ/KTV thuyết minh", "children": [], "modificationTime": now_ms, "tags": ["Phu_De_Whisper"], "icon": "folder", "iconColor": "blue"},
                {"id": F_VIDEO_ASMR, "name": "🎧 2.3 Video Âm Thanh ASMR (>4.5kHz)", "description": "Âm thanh dụng cụ sắc nét", "children": [], "modificationTime": now_ms, "tags": ["ASMR_Spa"], "icon": "folder", "iconColor": "purple"},
                {"id": F_VIDEO_BROLL, "name": "💆‍♀️ 2.4 Video B-Roll Thao Tác KTV", "description": "Cận cảnh liệu trình", "children": [], "modificationTime": now_ms, "tags": ["B-Roll_Liệu_Trình"], "icon": "folder", "iconColor": "green"},
                {"id": F_VIDEO_MUTE, "name": "🔇 2.5 Video Câm (Cần Lồng Nhạc BGM)", "description": "Footage lồng nhạc nền", "children": [], "modificationTime": now_ms, "tags": ["Video_Không_Tiếng"], "icon": "folder", "iconColor": "default"},
                {"id": F_VIDEO_CUSTOMERS, "name": f"👥 2.6 Video Khách Hàng Theo Album Thật ({len(video_cust_children)} Album)", "description": "Khớp 100% theo Album thật trên Google Photos", "children": video_cust_children, "modificationTime": now_ms, "tags": ["Video_Khách_Hàng"], "icon": "folder", "iconColor": "aqua"},
            ],
        },
    ]

    master_file = EAGLE_LIB / "metadata.json"
    master_data = json.loads(master_file.read_text(encoding="utf-8")) if master_file.exists() else {}
    master_data["folders"] = clean_tree
    master_data["modificationTime"] = now_ms
    master_file.write_text(json.dumps(master_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Refresh Eagle Windows cache so old tags/folders vanish immediately
    appdata = os.environ.get("APPDATA")
    if appdata:
        cache_dir = Path(appdata) / "Eagle" / "library-caches"
        if cache_dir.exists():
            all_metas = []
            for d in IMAGES_DIR.glob("*.info"):
                mf = d / "metadata.json"
                if mf.exists():
                    try:
                        all_metas.append(json.loads(mf.read_text(encoding="utf-8")))
                    except Exception:
                        pass
            for cf in cache_dir.glob("*.txt"):
                try:
                    cobj = json.loads(cf.read_text(encoding="utf-8"))
                    if isinstance(cobj, dict) and "items" in cobj:
                        cobj["items"] = all_metas
                        cf.write_text(json.dumps(cobj, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass

    return {
        "total_eagle_items": len(info_dirs),
        "cleaned_old_wrong_tags": cleaned_wrong_tags,
        "matched_real_album_items": matched_items,
        "general_library_items": unmatched_items,
        "real_photo_album_folders": len(photo_cust_children),
        "real_video_album_folders": len(video_cust_children),
    }


if __name__ == "__main__":
    scan_all_real_albums(force_rescan=False)
    by_key, by_label = load_real_album_lookup()
    print(f"✅ Tổng số khóa đối chiếu Album thật: {len(by_key):,} media_key | {len(by_label):,} exact timestamp labels", flush=True)
    summary = rebuild_eagle_clean_with_real_albums(by_key, by_label)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
