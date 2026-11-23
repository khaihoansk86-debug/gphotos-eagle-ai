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

    # =========================================================================
    # LAYER 2: DIRECT EAGLE DAM AI VISION INSPECTION & CLASSIFICATION
    # Works standalone on ANY Eagle library OR enriched with Layer-1 Photos context
    # =========================================================================
    @staticmethod
    def _find_eagle_preview_image(info_dir: Path, meta: Dict[str, Any]) -> Optional[Path]:
        """Finds the best viewable image (thumbnail or media file) inside an Eagle .info directory."""
        name = meta.get("name", "")
        ext = (meta.get("ext") or "").lower()
        # 1. Exact media image if it's a viewable raster image
        if ext in ("jpg", "jpeg", "png", "webp", "bmp"):
            exact = info_dir / f"{name}.{ext}"
            if exact.exists():
                return exact
        # 2. Eagle generated thumbnail (_thumbnail.png / _thumbnail.jpg)
        for cand in info_dir.glob("*_thumbnail.*"):
            if cand.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                return cand
        # 3. Any raster image in the .info folder
        for cand in info_dir.iterdir():
            if cand.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                return cand
        return None

    @staticmethod
    def _is_eagle_video(meta: Dict[str, Any]) -> bool:
        ext = (meta.get("ext") or "").lower()
        name = meta.get("name") or ""
        tags = meta.get("tags") or []
        folders = meta.get("folders") or []
        return (
            ext in ("mp4", "mov", "webm", "avi", "mkv")
            or F_ROOT_VIDEO in folders
            or name.startswith("Video")
            or any("Video" in t or "Reels" in t or "Hook" in t for t in tags)
        )

    def scan_eagle_library(self, eagle_lib_path: str = r"D:\test.library") -> Dict[str, Any]:
        """LAYER 2 AUDIT: Scans an Eagle library directly (standalone, no Google Photos required)."""
        eagle_lib = Path(eagle_lib_path)
        images_dir = eagle_lib / "images"
        if not images_dir.exists():
            raise ValueError(f"Eagle images folder not found: {images_dir}")

        total = 0
        photos = 0
        videos = 0
        ai_verified = 0
        has_real_album = 0
        missing_preview = 0

        for d in images_dir.glob("*.info"):
            mf = d / "metadata.json"
            if not mf.exists():
                continue
            try:
                meta = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("isDeleted"):
                continue
            total += 1
            if self._is_eagle_video(meta):
                videos += 1
            else:
                photos += 1
            tags = meta.get("tags") or []
            if "AI_Vision_Verified" in tags:
                ai_verified += 1
            if any(t.startswith("Khách:") for t in tags):
                has_real_album += 1
            if not self._find_eagle_preview_image(d, meta):
                missing_preview += 1

        unreviewed = max(0, total - ai_verified)
        return {
            "status": "success",
            "eagle_library": str(eagle_lib),
            "total_items": total,
            "photos": photos,
            "videos": videos,
            "ai_vision_verified": ai_verified,
            "unreviewed_remaining": unreviewed,
            "review_coverage_percent": round((ai_verified / total) * 100, 2) if total else 0.0,
            "with_real_photos_album_context": has_real_album,
            "missing_preview_image": missing_preview,
        }

    def get_eagle_review_sheet(
        self,
        eagle_lib_path: str = r"D:\test.library",
        batch_size: int = 20,
        kind: str = "all",
        only_unreviewed: bool = True,
    ) -> Tuple[Dict[str, Any], Optional[bytes]]:
        """
        LAYER 2 AI VISION: Reads up to 24 unreviewed items DIRECTLY from Eagle DAM
        and renders a numbered Contact Sheet JPEG + JSON metadata (including any Layer-1 Photos context).
        """
        batch_size = max(1, min(int(batch_size), 24))
        eagle_lib = Path(eagle_lib_path)
        images_dir = eagle_lib / "images"
        if not images_dir.exists():
            raise ValueError(f"Eagle images folder not found: {images_dir}")

        candidates = []
        total_unreviewed = 0

        for d in sorted(images_dir.glob("*.info")):
            mf = d / "metadata.json"
            if not mf.exists():
                continue
            try:
                meta = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("isDeleted"):
                continue
            tags = meta.get("tags") or []
            if only_unreviewed and "AI_Vision_Verified" in tags:
                continue
            is_vid = self._is_eagle_video(meta)
            item_kind = "video" if is_vid else "photo"
            if kind in ("photo", "video") and item_kind != kind:
                continue
            total_unreviewed += 1
            preview = self._find_eagle_preview_image(d, meta)
            if not preview:
                continue
            if len(candidates) < batch_size:
                candidates.append({
                    "eagle_id": meta.get("id") or d.stem,
                    "kind": item_kind,
                    "name": meta.get("name", ""),
                    "tags": tags,
                    "folders": meta.get("folders") or [],
                    "url": meta.get("url", ""),
                    "preview_path": preview,
                })

        if not candidates:
            return {
                "eagle_library": str(eagle_lib),
                "batch_count": 0,
                "remaining_unreviewed": total_unreviewed,
                "note": "All Eagle items in this filter have been visually reviewed by AI Vision!",
                "items": [],
            }, None

        cols = min(4, len(candidates))
        rows_n = math.ceil(len(candidates) / cols)
        tile_w, tile_h = 260, 290
        canvas = Image.new("RGB", (cols * tile_w, rows_n * tile_h), (18, 22, 32))
        draw = ImageDraw.Draw(canvas)

        meta_items = []
        for idx, it in enumerate(candidates):
            r_i, c_i = divmod(idx, cols)
            x0, y0 = c_i * tile_w, r_i * tile_h
            try:
                with Image.open(it["preview_path"]) as im:
                    thumb = ImageOps.fit(im.convert("RGB"), (tile_w - 8, tile_h - 36))
                    canvas.paste(thumb, (x0 + 4, y0 + 4))
            except Exception:
                draw.rectangle([x0 + 4, y0 + 4, x0 + tile_w - 4, y0 + tile_h - 36], fill=(40, 45, 60))

            badge_color = (220, 38, 38) if it["kind"] == "video" else (14, 165, 233)
            draw.rectangle([x0 + 8, y0 + 8, x0 + 96, y0 + 30], fill=badge_color)
            draw.text((x0 + 14, y0 + 13), f"#{idx + 1:02d} {'VID' if it['kind'] == 'video' else 'IMG'}", fill=(255, 255, 255))

            cust_tags = [t.replace("Khách:", "").strip() for t in it["tags"] if t.startswith("Khách:")]
            cap = f"#{idx + 1:02d} {cust_tags[0] if cust_tags else it['name'][:26]}"
            draw.text((x0 + 8, y0 + tile_h - 26), cap[:34], fill=(226, 232, 240))

            meta_items.append({
                "index": idx + 1,
                "eagle_id": it["eagle_id"],
                "kind": it["kind"],
                "name": it["name"],
                "customer_context": cust_tags,
                "current_tags": it["tags"],
                "url": it["url"],
            })

        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=86)
        payload = {
            "eagle_library": str(eagle_lib),
            "batch_count": len(meta_items),
            "remaining_unreviewed": total_unreviewed,
            "valid_photo_categories": ["hero", "before_after", "treatment", "facility", "archive"],
            "valid_video_categories": ["hook_3s", "speech", "asmr", "b_roll", "mute"],
            "instruction": (
                "Inspect every numbered Eagle tile (#01..#NN) visually, then call apply_eagle_vision_decisions "
                "with your business classification for EVERY eagle_id. Real customer album folders (AP_*/AV_*) and "
                "'Khách: ...' tags are preserved automatically while functional folders are cleanly replaced."
            ),
            "items": meta_items,
        }
        return payload, buf.getvalue()

    def apply_eagle_vision_decisions(
        self,
        eagle_lib_path: str = r"D:\test.library",
        decisions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        LAYER 2 WRITE (CLEAN OVERWRITE, ZERO STACKING):
        Replaces functional folders with AI Vision-verified business folders,
        preserves verified Layer-1 customer album folders (AP_*/AV_*) and 'Khách: ...' tags,
        and marks each item with 'AI_Vision_Verified'.
        """
        if not isinstance(decisions, list) or not decisions:
            raise ValueError("decisions must be a non-empty list of objects with eagle_id and category.")

        eagle_lib = Path(eagle_lib_path)
        images_dir = eagle_lib / "images"
        master_file = eagle_lib / "metadata.json"
        now_ms = int(time.time() * 1000)

        # Load existing Eagle folder tree so dynamic folder_names can match or auto-create
        master_data = json.loads(master_file.read_text(encoding="utf-8")) if master_file.exists() else {"folders": []}
        name_to_fid: Dict[str, str] = {}

        def index_folders(nodes):
            for n in nodes or []:
                nm = (n.get("name") or "").strip().lower()
                if nm and n.get("id"):
                    name_to_fid[nm] = n["id"]
                index_folders(n.get("children"))

        index_folders(master_data.get("folders"))
        tree_modified = False

        def resolve_or_create_folder(folder_name: str, is_vid: bool) -> str:
            nonlocal tree_modified
            key = folder_name.strip().lower()
            if key in name_to_fid:
                return name_to_fid[key]
            # Fuzzy substring match against existing folder names
            for existing_nm, fid in name_to_fid.items():
                if key in existing_nm or existing_nm in key:
                    return fid
            # Create new dynamic folder under Photo or Video root (or top-level if tree has custom roots)
            import hashlib
            new_id = ("DV_" if is_vid else "DP_") + hashlib.md5(key.encode("utf-8")).hexdigest().upper()[:10]
            new_node = {
                "id": new_id,
                "name": folder_name.strip(),
                "description": "Thư mục tạo động theo ngữ cảnh bởi AI Vision",
                "children": [],
                "modificationTime": now_ms,
                "tags": [],
                "icon": "folder",
                "iconColor": "default",
            }
            target_root_id = F_ROOT_VIDEO if is_vid else F_ROOT_PHOTO
            placed = False
            for root in master_data.setdefault("folders", []):
                if root.get("id") == target_root_id:
                    root.setdefault("children", []).append(new_node)
                    placed = True
                    break
            if not placed:
                master_data["folders"].append(new_node)
            name_to_fid[key] = new_id
            tree_modified = True
            return new_id

        photo_cat_map = {
            "hero": F_PHOTO_HERO,
            "before_after": F_PHOTO_BEFORE_AFTER,
            "treatment": F_PHOTO_TREATMENT,
            "facility": F_PHOTO_FACILITY,
            "archive": F_PHOTO_ARCHIVE,
        }
        video_cat_map = {
            "hook_3s": F_VIDEO_HOOK,
            "speech": F_VIDEO_SPEECH,
            "asmr": F_VIDEO_ASMR,
            "b_roll": F_VIDEO_BROLL,
            "mute": F_VIDEO_MUTE,
        }

        updated = 0
        not_found = 0
        for d in decisions:
            eid = str(d.get("eagle_id") or "").strip()
            if not eid:
                continue
            mf = images_dir / f"{eid}.info" / "metadata.json"
            if not mf.exists():
                not_found += 1
                continue
            meta = json.loads(mf.read_text(encoding="utf-8"))
            is_vid = self._is_eagle_video(meta)
            cat = str(d.get("category") or ("b_roll" if is_vid else "archive")).strip().lower()
            star = max(1, min(5, int(d.get("star") or (5 if cat in ("hero", "hook_3s") else 4))))
            ai_tags = d.get("tags") if isinstance(d.get("tags"), list) else []
            custom_folder_names = d.get("folder_names") if isinstance(d.get("folder_names"), list) else []
            summary = str(d.get("summary") or "").strip()
            capcut_note = str(d.get("capcut_note") or "").strip()

            # Preserve ONLY verified real customer folders (AP_*/AV_*)
            old_folders = meta.get("folders") or []
            preserved_customer_folders = [
                fid for fid in old_folders if str(fid).startswith("AP_") or str(fid).startswith("AV_")
            ]
            dynamic_fids = [resolve_or_create_folder(fn, is_vid) for fn in custom_folder_names if str(fn).strip()]
            if dynamic_fids:
                root_fid = F_ROOT_VIDEO if is_vid else F_ROOT_PHOTO
                new_folders = [root_fid, *dynamic_fids, *preserved_customer_folders]
            elif is_vid:
                new_folders = [F_ROOT_VIDEO, video_cat_map.get(cat, F_VIDEO_BROLL), *preserved_customer_folders]
            else:
                new_folders = [F_ROOT_PHOTO, photo_cat_map.get(cat, F_PHOTO_ARCHIVE), *preserved_customer_folders]

            # Preserve verified real customer tags (`Khách: ...`) + add clean AI tags + AI_Vision_Verified
            old_tags = meta.get("tags") or []
            preserved_customer_tags = [t for t in old_tags if t.startswith("Khách:")]
            base_tag = "Video_Dọc_9:16" if is_vid else "Ảnh_Tĩnh"
            new_tags = list(dict.fromkeys([base_tag, *preserved_customer_tags, *ai_tags, "AI_Vision_Verified"]))

            cust_str = ", ".join(t.replace("Khách:", "").strip() for t in preserved_customer_tags) or "Kho chung"
            url = meta.get("url") or ""
            annotation = (
                f"{'🎬 VIDEO' if is_vid else '📸 ẢNH'} · ĐÃ PHÂN LOẠI TRỰC TIẾP BỞI AI VISION (LỚP 2)\n"
                f"• Danh mục nghiệp vụ: {', '.join(custom_folder_names) if custom_folder_names else cat} ({star}⭐)\n"
                f"• Khách hàng (Album thật): {cust_str}\n"
                f"• Mô tả thị giác AI: {summary or meta.get('name', '')}\n"
                + (f"• 🎬 Gợi ý dựng CapCut: {capcut_note}\n" if capcut_note else "")
                + (f"• 🔗 Link gốc: {url}" if url else "")
            )

            meta["folders"] = list(dict.fromkeys(new_folders))
            meta["tags"] = new_tags
            meta["star"] = star
            meta["annotation"] = annotation
            meta["modificationTime"] = now_ms
            mf.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            updated += 1

        if tree_modified:
            master_data["modificationTime"] = now_ms
            master_file.write_text(json.dumps(master_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "status": "success",
            "eagle_library": str(eagle_lib),
            "updated_now": updated,
            "not_found": not_found,
            "tree_updated": tree_modified,
        }

    def get_eagle_folder_tree(self, eagle_lib_path: str = r"D:\test.library") -> Dict[str, Any]:
        """Reads the complete existing folder hierarchy of an Eagle library with live item counts."""
        eagle_lib = Path(eagle_lib_path)
        master_file = eagle_lib / "metadata.json"
        images_dir = eagle_lib / "images"
        if not master_file.exists():
            raise ValueError(f"Eagle metadata.json not found in: {eagle_lib}")

        master_data = json.loads(master_file.read_text(encoding="utf-8"))
        folder_counts: Dict[str, int] = {}
        if images_dir.exists():
            for d in images_dir.glob("*.info"):
                mf = d / "metadata.json"
                if not mf.exists():
                    continue
                try:
                    m = json.loads(mf.read_text(encoding="utf-8"))
                    if m.get("isDeleted"):
                        continue
                    for fid in m.get("folders") or []:
                        folder_counts[fid] = folder_counts.get(fid, 0) + 1
                except Exception:
                    continue

        def simplify(nodes):
            out = []
            for n in nodes or []:
                fid = n.get("id", "")
                out.append({
                    "id": fid,
                    "name": n.get("name", ""),
                    "item_count": folder_counts.get(fid, 0),
                    "children": simplify(n.get("children")),
                })
            return out

        tree = simplify(master_data.get("folders"))
        return {
            "status": "success",
            "eagle_library": str(eagle_lib),
            "root_count": len(tree),
            "folders": tree,
        }

    def get_eagle_item_detail(
        self,
        eagle_id: str,
        eagle_lib_path: str = r"D:\test.library",
        max_dim: int = 1200,
    ) -> Tuple[Dict[str, Any], Optional[bytes]]:
        """
        HIGH-RES ZOOM + CONTEXT NEIGHBORS:
        Returns ONE crisp high-res JPEG (up to 1200px) as ImageContent plus full metadata
        and chronological neighbor items (before/after) so AI can read fine text or judge Before-After accurately.
        """
        eagle_lib = Path(eagle_lib_path)
        images_dir = eagle_lib / "images"
        info_dir = images_dir / f"{eagle_id}.info"
        mf = info_dir / "metadata.json"
        if not mf.exists():
            raise ValueError(f"Eagle item not found: {eagle_id}")

        meta = json.loads(mf.read_text(encoding="utf-8"))
        preview = self._find_eagle_preview_image(info_dir, meta)

        img_bytes = None
        if preview and preview.exists():
            with Image.open(preview) as im:
                rgb = im.convert("RGB")
                rgb.thumbnail((max_dim, max_dim))
                buf = io.BytesIO()
                rgb.save(buf, format="JPEG", quality=90)
                img_bytes = buf.getvalue()

        # Find chronological neighbors by parsed timestamp in name (same day / session)
        from session_clusterer import parse_label_datetime
        target_dt = parse_label_datetime(meta.get("name", ""))
        neighbors = []
        if target_dt:
            scored = []
            for d in images_dir.glob("*.info"):
                if d.stem == eagle_id:
                    continue
                nmf = d / "metadata.json"
                if not nmf.exists():
                    continue
                try:
                    nm = json.loads(nmf.read_text(encoding="utf-8"))
                    ndt = parse_label_datetime(nm.get("name", ""))
                    if ndt:
                        diff_sec = (ndt - target_dt).total_seconds()
                        if abs(diff_sec) <= 2100:  # within 35-min session window
                            scored.append((diff_sec, nm.get("id") or d.stem, nm.get("name", ""), nm.get("tags") or []))
                except Exception:
                    continue
            before = sorted([x for x in scored if x[0] < 0], key=lambda x: x[0], reverse=True)[:2]
            after = sorted([x for x in scored if x[0] > 0], key=lambda x: x[0])[:2]
            for diff_sec, nid, nname, ntags in reversed(before):
                neighbors.append({"relation": "before", "delta_seconds": int(diff_sec), "eagle_id": nid, "name": nname, "tags": ntags})
            for diff_sec, nid, nname, ntags in after:
                neighbors.append({"relation": "after", "delta_seconds": int(diff_sec), "eagle_id": nid, "name": nname, "tags": ntags})

        payload = {
            "eagle_id": meta.get("id") or eagle_id,
            "name": meta.get("name", ""),
            "ext": meta.get("ext", ""),
            "kind": "video" if self._is_eagle_video(meta) else "photo",
            "star": meta.get("star", 0),
            "width": meta.get("width", 0),
            "height": meta.get("height", 0),
            "tags": meta.get("tags") or [],
            "folders": meta.get("folders") or [],
            "url": meta.get("url", ""),
            "annotation": meta.get("annotation", ""),
            "session_neighbors_within_35min": neighbors,
        }
        return payload, img_bytes

    def get_video_storyboard(
        self,
        eagle_id_or_path: str,
        eagle_lib_path: str = r"D:\test.library",
        interval_seconds: int = 10,
        start_second: int = 0,
        max_frames: int = 24,
    ) -> Tuple[Dict[str, Any], Optional[bytes]]:
        """
        THOROUGH 10-SECOND INTERVAL VIDEO SCRUBBING ALL THE WAY TO CLIP END:
        Extracts 1 frame every `interval_seconds` (default 10s) from start to end of a real local video
        (plus 00:01 & 00:03 for Hook 3s check, and the final second of the clip) into ONE timestamped
        Storyboard JPEG (ImageContent) + Faster-Whisper Vietnamese speech & ASMR >4.5kHz intel.
        For clips longer than `max_frames * interval_seconds` (>4 mins), returns `has_more=True` and
        `next_start_second` so the AI inspects 100% of the clip to the very end before concluding.
        """
        interval_seconds = max(2, min(int(interval_seconds), 30))
        start_second = max(0, int(start_second))
        max_frames = max(4, min(int(max_frames), 24))

        p = Path(eagle_id_or_path)
        video_file: Optional[Path] = p if (p.exists() and p.suffix.lower() in (".mp4", ".mov", ".webm", ".avi", ".mkv")) else None
        cover_fallback: Optional[Path] = None
        meta_info: Dict[str, Any] = {}

        if not video_file:
            eagle_lib = Path(eagle_lib_path)
            info_dir = eagle_lib / "images" / f"{eagle_id_or_path}.info"
            mf = info_dir / "metadata.json"
            if mf.exists():
                meta_info = json.loads(mf.read_text(encoding="utf-8"))
                for f in info_dir.iterdir():
                    if f.suffix.lower() in (".mp4", ".mov", ".webm", ".avi", ".mkv"):
                        video_file = f
                        break
                cover_fallback = self._find_eagle_preview_image(info_dir, meta_info)

        if not video_file:
            img_bytes = None
            if cover_fallback and cover_fallback.exists():
                with Image.open(cover_fallback) as im:
                    rgb = im.convert("RGB")
                    rgb.thumbnail((900, 900))
                    buf = io.BytesIO()
                    rgb.save(buf, format="JPEG", quality=88)
                    img_bytes = buf.getvalue()
            return {
                "status": "cover_only",
                "is_real_video_file": False,
                "eagle_id": eagle_id_or_path,
                "name": meta_info.get("name", ""),
                "url": meta_info.get("url", ""),
                "note": "Mục này trong Eagle hiện chỉ lưu ảnh bìa .jpg + link Google Photos (chưa có file .mp4 gốc trên ổ cứng). Đã trả về ảnh bìa nét cao để AI xem.",
            }, img_bytes

        import cv2
        cap = cv2.VideoCapture(str(video_file))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = total_frames / fps if fps > 0 else 0.0

        # Build exact sampling schedule: Hook (1s, 3s) + every 10s all the way to end
        sample_secs: List[float] = []
        if duration <= 0.5:
            sample_secs = [0.0]
        else:
            if start_second == 0:
                if duration > 1.0:
                    sample_secs.append(1.0)
                if duration > 3.5:
                    sample_secs.append(3.0)
                t = float(interval_seconds)
            else:
                t = float(start_second)

            while t < duration - 0.5:
                sample_secs.append(t)
                t += float(interval_seconds)

            # Always include near-end frame so AI sees the conclusion of the clip
            end_sec = max(0.0, duration - 0.5)
            if not sample_secs or (end_sec - sample_secs[-1]) >= 2.0:
                sample_secs.append(end_sec)

            # For very short clips (<10s), ensure at least 4 evenly spaced frames
            if start_second == 0 and len(sample_secs) < 4 and duration >= 2.0:
                sample_secs = [round((i + 0.5) * duration / 4.0, 1) for i in range(4)]

        has_more = len(sample_secs) > max_frames
        page_secs = sample_secs[:max_frames]
        next_start_second = int(sample_secs[max_frames]) if has_more else None

        cols = 4 if len(page_secs) > 9 else 3
        rows_n = math.ceil(len(page_secs) / cols)
        tile_w, tile_h = 280, 280
        canvas = Image.new("RGB", (cols * tile_w, rows_n * tile_h), (14, 18, 28))
        draw = ImageDraw.Draw(canvas)
        timestamps = []

        for idx, ts_sec in enumerate(page_secs):
            frame_no = min(max(0, total_frames - 1), int(ts_sec * fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, bgr = cap.read()
            ts_str = f"{int(ts_sec // 60):02d}:{int(ts_sec % 60):02d}"
            timestamps.append(ts_str)
            r_i, c_i = divmod(idx, cols)
            x0, y0 = c_i * tile_w, r_i * tile_h
            if ok and bgr is not None:
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                pil_im = ImageOps.fit(Image.fromarray(rgb), (tile_w - 6, tile_h - 6))
                canvas.paste(pil_im, (x0 + 3, y0 + 3))
            draw.rectangle([x0 + 8, y0 + 8, x0 + 96, y0 + 30], fill=(0, 0, 0))
            draw.text((x0 + 14, y0 + 13), f"#{idx + 1} {ts_str}", fill=(255, 255, 255))
        cap.release()

        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=85)

        audio_intel = {}
        if start_second == 0:
            try:
                from video_analyzer import VideoAnalyzer
                audio_intel = VideoAnalyzer.compile_video_intelligence(str(video_file))
            except Exception:
                pass

        return {
            "status": "success",
            "is_real_video_file": True,
            "video_path": str(video_file),
            "duration_seconds": round(duration, 1),
            "interval_seconds": interval_seconds,
            "frames_extracted": len(page_secs),
            "timestamps": timestamps,
            "has_more": has_more,
            "next_start_second": next_start_second,
            "instruction": (
                f"Clip dài {round(duration, 1)}s. Nếu has_more=true, BẮT BUỘC gọi tiếp get_video_storyboard(..., start_second={next_start_second}) "
                "để xem đủ từng mốc 10 giây tới hết clip trước khi đưa ra kết luận phân loại!"
                if has_more
                else f"Đã xem đủ toàn bộ {round(duration, 1)}s của clip theo mốc {interval_seconds} giây tới tận cuối clip. Có thể kết luận phân loại ngay."
            ),
            "audio_and_whisper_intel": audio_intel,
        }, buf.getvalue()

    def search_eagle_items(
        self,
        eagle_lib_path: str = r"D:\test.library",
        keyword: str = "",
        tag: str = "",
        folder: str = "",
        kind: str = "all",
        min_star: int = 0,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """Fast local query directly over Eagle DAM to retrieve classified assets for content production."""
        eagle_lib = Path(eagle_lib_path)
        images_dir = eagle_lib / "images"
        master_file = eagle_lib / "metadata.json"
        if not images_dir.exists():
            raise ValueError(f"Eagle images folder not found: {images_dir}")

        fid_to_name: Dict[str, str] = {}
        if master_file.exists():
            md = json.loads(master_file.read_text(encoding="utf-8"))
            def walk(nodes):
                for n in nodes or []:
                    fid_to_name[n.get("id", "")] = n.get("name", "")
                    walk(n.get("children"))
            walk(md.get("folders"))

        kw = (keyword or "").strip().lower()
        tg = (tag or "").strip().lower()
        fl = (folder or "").strip().lower()
        limit = max(1, min(int(limit), 100))

        matches = []
        for d in images_dir.glob("*.info"):
            mf = d / "metadata.json"
            if not mf.exists():
                continue
            try:
                m = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if m.get("isDeleted"):
                continue
            item_kind = "video" if self._is_eagle_video(m) else "photo"
            if kind in ("photo", "video") and item_kind != kind:
                continue
            if int(m.get("star") or 0) < int(min_star):
                continue
            tags = m.get("tags") or []
            f_names = [fid_to_name.get(fid, fid) for fid in (m.get("folders") or [])]
            if tg and not any(tg in t.lower() for t in tags):
                continue
            if fl and not any(fl in fn.lower() for fn in f_names):
                continue
            if kw:
                hay = f"{m.get('name', '')} {m.get('annotation', '')} {' '.join(tags)} {' '.join(f_names)}".lower()
                if kw not in hay:
                    continue
            matches.append({
                "eagle_id": m.get("id") or d.stem,
                "name": m.get("name", ""),
                "kind": item_kind,
                "star": m.get("star", 0),
                "tags": tags,
                "folders": f_names,
                "url": m.get("url", ""),
            })

        matches.sort(key=lambda x: x["star"], reverse=True)
        return {
            "status": "success",
            "eagle_library": str(eagle_lib),
            "total_matches": len(matches),
            "returned": len(matches[:limit]),
            "items": matches[:limit],
        }
