"""
Backend MCP Engine for 100% Full-Coverage AI Visual Inspection & Classification.
Enables any AI Agent connected via MCP to:
  1. Prefetch all missing thumbnails in parallel via Chrome DevTools bridge.
  2. Track exact durable classification coverage in SQLite (photo_classifications).
  3. Pull high-density numbered Contact Sheets (up to 24 unclassified items/sheet)
     with 35-min session context so the AI visually inspects 100% of the library.
  4. Submit structured batch classifications atomically (Zero-Drop).
  5. Materialize 100% of AI-verified classifications into the 2-branch Eagle DAM tree.
"""

import io
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageOps

from session_clusterer import SessionClusterer
from reorganize_eagle_tree import (
    VIP_CUSTOMERS,
    F_ROOT_PHOTO, F_PHOTO_HERO, F_PHOTO_BEFORE_AFTER, F_PHOTO_TREATMENT, F_PHOTO_FACILITY,
    F_ROOT_VIDEO, F_VIDEO_HOOK, F_VIDEO_SPEECH, F_VIDEO_ASMR, F_VIDEO_BROLL, F_VIDEO_MUTE,
    get_customer_for_item,
)
from full_sync_eagle import (
    F_PHOTO_ARCHIVE,
    ensure_tree_with_archive,
    sanitize_filename,
    get_image_dimensions,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "v2" / "data"
THUMBS_DIR = DATA_DIR / "photos_thumbs"


class AIClassificationEngine:
    def __init__(self, store):
        self.store = store
        self._init_schema()

    def _init_schema(self):
        with self.store.connect(True) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS photo_classifications (
                    item_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    category TEXT NOT NULL,
                    star INTEGER NOT NULL DEFAULT 4,
                    customer_id TEXT DEFAULT '',
                    customer_name TEXT DEFAULT '',
                    phase TEXT DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    summary TEXT DEFAULT '',
                    capcut_note TEXT DEFAULT '',
                    updated REAL NOT NULL
                )
            """)
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_photo_cls_profile ON photo_classifications(profile_id, category)"
            )

    def prefetch_thumbnails(self, profile_id: str, limit: int = 500, concurrency: int = 10) -> Dict[str, Any]:
        """Batch-downloads missing thumbnails from Google Photos via the open Chrome profile."""
        THUMBS_DIR.mkdir(parents=True, exist_ok=True)
        with self.store.connect() as db:
            prof = db.execute("SELECT id, name, path FROM profiles WHERE id=?", (profile_id,)).fetchone()
            if not prof:
                raise ValueError(f"Profile not found: {profile_id}")
            rows = db.execute(
                "SELECT id, body FROM photos_items WHERE profile_id=? ORDER BY rowid ASC",
                (profile_id,),
            ).fetchall()

        missing = []
        cached_before = 0
        for r in rows:
            item_id = r["id"]
            b = json.loads(r["body"])
            out_path = THUMBS_DIR / f"{item_id}.jpg"
            if out_path.exists():
                cached_before += 1
            elif b.get("thumbnail_url"):
                missing.append({
                    "id": item_id,
                    "url": b["thumbnail_url"],
                    "out_path": str(out_path),
                })

        batch = missing[: max(1, min(int(limit), 5000))]
        if not batch:
            return {
                "status": "complete",
                "total_items": len(rows),
                "cached_total": cached_before,
                "remaining_missing": 0,
                "downloaded_now": 0,
                "failed_now": 0,
            }

        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required for batch prefetch.")
        script = str(BASE_DIR / "photos_batch_fetch.js")
        proc = subprocess.run(
            [node, script, prof["path"]],
            input=json.dumps({"items": batch, "concurrency": max(1, min(int(concurrency), 15))}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "Failed to prefetch thumbnails via Chrome bridge.")

        ok_cnt = 0
        fail_cnt = 0
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if ev.get("event") in ("progress", "complete"):
                    ok_cnt = ev.get("ok", ok_cnt)
                    fail_cnt = ev.get("failed", fail_cnt)
            except Exception:
                pass

        return {
            "status": "success",
            "total_items": len(rows),
            "cached_total": cached_before + ok_cnt,
            "remaining_missing": max(0, len(missing) - ok_cnt),
            "downloaded_now": ok_cnt,
            "failed_now": fail_cnt,
        }

    def get_progress(self, profile_id: str) -> Dict[str, Any]:
        """Returns exact 100%-coverage audit: total items, cached thumbs, AI-classified vs remaining."""
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT id, body FROM photos_items WHERE profile_id=?",
                (profile_id,),
            ).fetchall()
            cls_rows = db.execute(
                "SELECT item_id, kind, category, star FROM photo_classifications WHERE profile_id=?",
                (profile_id,),
            ).fetchall()

        total = len(rows)
        photos_total = 0
        videos_total = 0
        cached_thumbs = 0
        for r in rows:
            b = json.loads(r["body"])
            if b.get("kind") == "video":
                videos_total += 1
            else:
                photos_total += 1
            if (THUMBS_DIR / f"{r['id']}.jpg").exists():
                cached_thumbs += 1

        cls_ids = {r["item_id"] for r in cls_rows}
        by_category: Dict[str, int] = {}
        cls_photos = 0
        cls_videos = 0
        for r in cls_rows:
            cat = r["category"]
            by_category[cat] = by_category.get(cat, 0) + 1
            if r["kind"] == "video":
                cls_videos += 1
            else:
                cls_photos += 1

        classified_count = len(cls_ids)
        unclassified_count = max(0, total - classified_count)
        coverage_pct = round((classified_count / total) * 100, 2) if total else 0.0

        return {
            "profile_id": profile_id,
            "total_items": total,
            "photos_total": photos_total,
            "videos_total": videos_total,
            "cached_thumbs": cached_thumbs,
            "missing_thumbs": max(0, total - cached_thumbs),
            "classified_count": classified_count,
            "classified_photos": cls_photos,
            "classified_videos": cls_videos,
            "unclassified_count": unclassified_count,
            "coverage_percent": coverage_pct,
            "breakdown_by_category": by_category,
        }

    def get_unclassified_contact_sheet(
        self,
        profile_id: str,
        batch_size: int = 20,
        kind: str = "all",
        only_cached: bool = True,
    ) -> Tuple[Dict[str, Any], Optional[bytes]]:
        """
        Fetches the next N unclassified items and renders a high-density numbered
        Contact Sheet JPEG so the AI Agent visually inspects every single item.
        """
        batch_size = max(1, min(int(batch_size), 24))
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT id, body FROM photos_items WHERE profile_id=? ORDER BY rowid ASC",
                (profile_id,),
            ).fetchall()
            done_ids = {
                r["item_id"]
                for r in db.execute(
                    "SELECT item_id FROM photo_classifications WHERE profile_id=?",
                    (profile_id,),
                ).fetchall()
            }

        # Build session hints across all items (fast 0.05s)
        all_raw = []
        for r in rows:
            b = json.loads(r["body"])
            all_raw.append({
                "id": r["id"],
                "kind": b.get("kind", "photo"),
                "label": b.get("label", ""),
                "photo_url": b.get("photo_url", ""),
                "duration": b.get("duration", ""),
                "thumbnail_url": b.get("thumbnail_url", ""),
            })

        clusterer = SessionClusterer(max_gap_seconds=2100)
        sessions = clusterer.enrich_sessions_with_customers(clusterer.cluster(all_raw), VIP_CUSTOMERS)

        session_lookup = {}
        for s in sessions:
            for it in s["items"]:
                session_lookup[it["id"]] = {
                    "session_id": s["session_id"],
                    "customer_id": it.get("customer_id") or "",
                    "customer_name": it.get("customer_name") or "",
                    "phase": it.get("phase") or "in_process",
                }

        candidates = []
        total_unclassified = 0
        for it in all_raw:
            if it["id"] in done_ids:
                continue
            if kind in ("photo", "video") and it["kind"] != kind:
                continue
            total_unclassified += 1
            tpath = THUMBS_DIR / f"{it['id']}.jpg"
            if only_cached and not tpath.exists():
                continue
            if len(candidates) < batch_size:
                hint = session_lookup.get(it["id"], {})
                candidates.append({**it, **hint, "thumb_path": tpath})

        if not candidates:
            return {
                "profile_id": profile_id,
                "batch_count": 0,
                "remaining_unclassified": total_unclassified,
                "note": (
                    "No cached unclassified items left. Call prefetch_all_photo_thumbnails first if missing_thumbs > 0."
                    if total_unclassified > 0
                    else "100% of items in this profile have been classified!"
                ),
                "items": [],
            }, None

        # Render crisp numbered contact sheet (4 columns x N rows)
        cols = min(4, len(candidates))
        rows_n = math.ceil(len(candidates) / cols)
        tile_w, tile_h = 260, 290
        canvas = Image.new("RGB", (cols * tile_w, rows_n * tile_h), (18, 22, 32))
        draw = ImageDraw.Draw(canvas)

        meta_items = []
        for idx, it in enumerate(candidates):
            r_i, c_i = divmod(idx, cols)
            x0, y0 = c_i * tile_w, r_i * tile_h
            tpath: Path = it["thumb_path"]
            if tpath.exists():
                try:
                    with Image.open(tpath) as im:
                        thumb = ImageOps.fit(im.convert("RGB"), (tile_w - 8, tile_h - 36))
                        canvas.paste(thumb, (x0 + 4, y0 + 4))
                except Exception:
                    draw.rectangle([x0 + 4, y0 + 4, x0 + tile_w - 4, y0 + tile_h - 36], fill=(40, 45, 60))
            else:
                draw.rectangle([x0 + 4, y0 + 4, x0 + tile_w - 4, y0 + tile_h - 36], fill=(40, 45, 60))

            # Top-left index badge (#01 IMG / #02 VID)
            badge_color = (220, 38, 38) if it["kind"] == "video" else (14, 165, 233)
            draw.rectangle([x0 + 8, y0 + 8, x0 + 96, y0 + 30], fill=badge_color)
            tag_lbl = f"#{idx + 1:02d} {'VID' if it['kind'] == 'video' else 'IMG'}"
            draw.text((x0 + 14, y0 + 13), tag_lbl, fill=(255, 255, 255))

            # Bottom caption strip
            cap = f"#{idx + 1:02d} {it.get('customer_id') or it.get('session_id', '')} | {it.get('phase', '')}"
            draw.text((x0 + 8, y0 + tile_h - 26), cap[:34], fill=(226, 232, 240))

            meta_items.append({
                "index": idx + 1,
                "item_id": it["id"],
                "kind": it["kind"],
                "label": it["label"],
                "duration": it["duration"],
                "session_id": it.get("session_id", ""),
                "customer_id_hint": it.get("customer_id", ""),
                "customer_name_hint": it.get("customer_name", ""),
                "phase_hint": it.get("phase", ""),
                "photo_url": it["photo_url"],
            })

        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=86)
        payload = {
            "profile_id": profile_id,
            "batch_count": len(meta_items),
            "remaining_unclassified": total_unclassified,
            "valid_photo_categories": ["hero", "before_after", "treatment", "facility", "archive"],
            "valid_video_categories": ["hook_3s", "speech", "asmr", "b_roll", "mute"],
            "instruction": (
                "Inspect every numbered tile (#01..#NN) visually, then call submit_photo_classifications "
                "with a decision for EVERY item_id in this batch (Zero-Drop: do not skip any item)."
            ),
            "items": meta_items,
        }
        return payload, buf.getvalue()

    def submit_classifications(self, profile_id: str, decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Atomically persists AI visual classifications for a batch of Google Photos items."""
        if not isinstance(decisions, list) or not decisions:
            raise ValueError("decisions must be a non-empty list of classification objects.")

        now = time.time()
        saved = 0
        with self.store.connect(True) as db:
            for d in decisions:
                item_id = str(d.get("item_id") or "").strip()
                if not item_id:
                    continue
                row = db.execute(
                    "SELECT body FROM photos_items WHERE id=? AND profile_id=?",
                    (item_id, profile_id),
                ).fetchone()
                if not row:
                    continue
                body = json.loads(row["body"])
                kind = str(d.get("kind") or body.get("kind") or "photo")
                category = str(d.get("category") or ("b_roll" if kind == "video" else "archive")).strip().lower()
                star = max(1, min(5, int(d.get("star") or (5 if category in ("hero", "hook_3s") else 4))))
                customer_id = str(d.get("customer_id") or "").strip()
                customer_name = str(d.get("customer_name") or "").strip()
                phase = str(d.get("phase") or "").strip()
                tags = d.get("tags") if isinstance(d.get("tags"), list) else []
                summary = str(d.get("summary") or "").strip()
                capcut_note = str(d.get("capcut_note") or "").strip()

                db.execute(
                    """
                    INSERT OR REPLACE INTO photo_classifications
                    (item_id, profile_id, kind, category, star, customer_id, customer_name, phase, tags_json, summary, capcut_note, updated)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        item_id, profile_id, kind, category, star,
                        customer_id, customer_name, phase,
                        json.dumps(tags, ensure_ascii=False),
                        summary, capcut_note, now,
                    ),
                )
                saved += 1

        prog = self.get_progress(profile_id)
        return {
            "status": "success",
            "saved_now": saved,
            "progress": prog,
        }

    def apply_classifications_to_eagle(self, profile_id: str, eagle_lib_path: str = r"D:\test.library") -> Dict[str, Any]:
        """
        Writes 100% of AI-classified items (from photo_classifications) into the strict 2-branch Eagle DAM tree,
        enforcing the Deterministic File Contract (0 broken thumbnails).
        """
        eagle_lib = Path(eagle_lib_path)
        images_dir = eagle_lib / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        ensure_tree_with_archive(eagle_lib)

        with self.store.connect() as db:
            rows = db.execute(
                """
                SELECT c.*, p.body
                FROM photo_classifications c
                JOIN photos_items p ON p.id = c.item_id AND p.profile_id = c.profile_id
                WHERE c.profile_id = ?
                """,
                (profile_id,),
            ).fetchall()

        now_ms = int(time.time() * 1000)
        written_photos = 0
        written_videos = 0
        missing_thumb = 0

        for r in rows:
            item_id = r["item_id"]
            tpath = THUMBS_DIR / f"{item_id}.jpg"
            if not tpath.exists():
                missing_thumb += 1
                continue

            body = json.loads(r["body"])
            lbl = body.get("label", "")
            photo_url = body.get("photo_url", "")
            kind = r["kind"]
            cat = r["category"]
            star = r["star"]
            cid = r["customer_id"]
            cname = r["customer_name"]
            phase = r["phase"]
            tags = json.loads(r["tags_json"] or "[]")
            summary = r["summary"]
            capcut_note = r["capcut_note"]

            if not cid:
                cid, cname = get_customer_for_item(lbl, tags)

            eagle_id = item_id[:13].upper()
            info_dir = images_dir / f"{eagle_id}.info"
            info_dir.mkdir(parents=True, exist_ok=True)

            clean_name = sanitize_filename(lbl, eagle_id)
            dest_img = info_dir / f"{clean_name}.jpg"
            for existing in info_dir.glob("*.jpg"):
                if existing.name != dest_img.name:
                    try:
                        existing.unlink()
                    except Exception:
                        pass
            if not dest_img.exists() or dest_img.stat().st_size != tpath.stat().st_size:
                shutil.copy2(tpath, dest_img)

            w, h = get_image_dimensions(dest_img)
            fsize = dest_img.stat().st_size

            folders = []
            if kind == "video":
                written_videos += 1
                folders.append(F_ROOT_VIDEO)
                cat_map = {
                    "hook_3s": F_VIDEO_HOOK,
                    "speech": F_VIDEO_SPEECH,
                    "asmr": F_VIDEO_ASMR,
                    "mute": F_VIDEO_MUTE,
                    "b_roll": F_VIDEO_BROLL,
                }
                folders.append(cat_map.get(cat, F_VIDEO_BROLL))
                if cid:
                    folders.append(f"MV_{cid.upper()[:10]}")
            else:
                written_photos += 1
                folders.append(F_ROOT_PHOTO)
                cat_map = {
                    "hero": F_PHOTO_HERO,
                    "before_after": F_PHOTO_BEFORE_AFTER,
                    "treatment": F_PHOTO_TREATMENT,
                    "facility": F_PHOTO_FACILITY,
                    "archive": F_PHOTO_ARCHIVE,
                }
                folders.append(cat_map.get(cat, F_PHOTO_ARCHIVE))
                if cid:
                    folders.append(f"MP_{cid.upper()[:10]}")

            if cid and f"Khách_{cid}" not in tags:
                tags.append(f"Khách_{cid}")

            annotation = (
                f"{'🎬 VIDEO' if kind == 'video' else '📸 ẢNH'} · PHÂN LOẠI TRỰC TIẾP BỞI AI VISION\n"
                f"• Danh mục: {cat} ({star}⭐)\n"
                f"• Khách hàng: {cname or cid or 'Chung'}\n"
                f"• Giai đoạn: {phase or 'Chưa phân đoạn'}\n"
                f"• Mô tả AI: {summary or lbl}\n"
                + (f"• 🎬 Gợi ý dựng CapCut: {capcut_note}\n" if capcut_note else "")
                + f"• 🔗 Link gốc Google Photos: {photo_url}"
            )

            meta = {
                "id": eagle_id,
                "name": clean_name,
                "size": fsize,
                "btime": now_ms,
                "mtime": now_ms,
                "ext": "jpg",
                "tags": list(dict.fromkeys(tags)),
                "folders": list(dict.fromkeys(folders)),
                "isDeleted": False,
                "url": photo_url,
                "annotation": annotation,
                "modificationTime": now_ms,
                "height": h,
                "width": w,
                "star": star,
                "noThumbnail": True,
                "lastModified": now_ms,
            }
            (info_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "status": "success",
            "eagle_library": str(eagle_lib),
            "written_photos": written_photos,
            "written_videos": written_videos,
            "written_total": written_photos + written_videos,
            "missing_thumb_skipped": missing_thumb,
        }
