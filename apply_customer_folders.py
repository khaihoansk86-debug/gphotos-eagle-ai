import os
import sys
import json
import glob
import time
import urllib.request
from typing import Optional
from taxonomy_manager import TaxonomyManager
from vision_enricher import VisionEnricher
from quality_scorer import QualityScorer
from journey_classifier import JourneyClassifier
from tool_detector import ToolDetector

LIBRARY_PATH = r"D:\test.library"
IMAGES_DIR = os.path.join(LIBRARY_PATH, "images")
CACHE_FILE = os.path.expandvars(r"%APPDATA%\Eagle\library-caches\5d59398c.txt")

# Functional category folder IDs
FOLDERS = {
    "hook": "MWEBFYK9AGVM8",         # 01_Hook 3s & Cận cảnh da
    "treatment": "MWEB2B79G65JQ",    # 02_B-Roll Liệu trình & Bác sĩ thao tác
    "feedback": "MWEBFYJUFO00R",     # 03_Feedback & Khách hàng trải nghiệm
    "facility": "MWEBFYJMIEN5C",     # 04_Cơ sở vật chất & Đội ngũ Spa
    "video": "MWEB2B9FXRSWX"         # 05_Raw Video Footage
}

# Mapping date sessions to Customer Folders and Customer Tags
CUSTOMER_MAP = {
    "12 thg 11, 2026": {
        "name": "Thu Lee - 0967033270",
        "folder_id": "MFCB777C3AD1F",
        "tag": "Khách_ThuLee"
    },
    "3 thg 10, 2026": {
        "name": "Chị Ngọc",
        "folder_id": "MCC9BA14023B1",
        "tag": "Khách_ChịNgọc"
    },
    "23 thg 10, 2026": {
        "name": "Nguyễn Thị Kim Ngân 0987601974",
        "folder_id": "M60173DA47DF2",
        "tag": "Khách_KimNgân"
    },
    "28 thg 10, 2026": {
        "name": "Chị Phương b c Ngọc",
        "folder_id": "MWEOV79AYBTBB",
        "tag": "Khách_ChịPhương"
    },
    "25 thg 9, 2026": {
        "name": "Ng T Xinh",
        "folder_id": "MWEOV79INZFEV",
        "tag": "Khách_NgTXinh"
    },
    "10 thg 10, 2026": {
        "name": "Phan Thị Hạnh",
        "folder_id": "MA29FF2631BC6",
        "tag": "Khách_PhanHạnh"
    },
    "26 thg 10, 2026": {
        "name": "Châu Thị Ngọc Thúy - 0944840188",
        "folder_id": "MWEOV79ZHTKBY",
        "tag": "Khách_NgọcThúy"
    },
    "2 thg 10, 2026": {
        "name": "Ngô Phương - 0937024555",
        "folder_id": "MWEOV7A8A1VFL",
        "tag": "Khách_NgôPhương"
    },
    "7 thg 10, 2026": {
        "name": "Xuân Hương",
        "folder_id": "M6231C3D72C77",
        "tag": "Khách_XuânHương"
    },
    "5 thg 11, 2026": {
        "name": "Lê Ng Hồng Nhung 0393439625",
        "folder_id": "MWEOV7AQMKRHA",
        "tag": "Khách_HồngNhung"
    },
    "20 thg 9, 2026": {
        "name": "Phan T Kim Oanh 0937370664",
        "folder_id": "MWEOV7AXSRMEC",
        "tag": "Khách_KimOanh"
    },
    "22 thg 10, 2026": {
        "name": "Ngô Thị Út 0387494003",
        "folder_id": "MWEOV7B6MK54S",
        "tag": "Khách_NgôÚt"
    },
    "8 thg 11, 2026": {
        "name": "Trần T Thanh Nhàn 0334412337",
        "folder_id": "MWEOV7BGK6GCE",
        "tag": "Khách_ThanhNhàn"
    },
    "6 thg 10, 2026": {
        "name": "Nguyễn Thị Thanh Tuyền 0938049398",
        "folder_id": "MWEOV7BOHK3K8",
        "tag": "Khách_ThanhTuyền"
    },
    "12 thg 10, 2026": {
        "name": "Bùi Thái Quỳnh Thi 0912503340",
        "folder_id": "MWEOV7BWHXSDV",
        "tag": "Khách_QuỳnhThi"
    },
    "9 thg 10, 2026": {
        "name": "Võ T Thanh Tuyền cf muối",
        "folder_id": "MWEOV7C4YQEEC",
        "tag": "Khách_ThanhTuyềnCfMuối"
    },
    "29 thg 10, 2026": {
        "name": "Võ Thành Ý 0901666827",
        "folder_id": "MWEOV7CCB3DHQ",
        "tag": "Khách_ThànhÝ"
    },
    "17 thg 10, 2026": {
        "name": "Trần Thị Nhã Linh - 0944280229",
        "folder_id": "MWEOV7CJ312XK",
        "tag": "Khách_NhãLinh"
    },
    "24 thg 10, 2026": {
        "name": "Nguyễn Hoàng Phi 0911486119",
        "folder_id": "MWEOV7E30X4UI",
        "tag": "Khách_HoàngPhi"
    },
    "11 thg 10, 2026": {
        "name": "Lê Thị Hồng Hoa 0869223630",
        "folder_id": "MWEOV7ECS1VPJ",
        "tag": "Khách_HồngHoa"
    }
}


def run(library_path: str = None):
    lib_path = library_path or LIBRARY_PATH
    images_dir = os.path.join(lib_path, "images")
    print(f"🚀 Bắt đầu làm giàu chuyên sâu: 1-5 Sao Quality, Tiến Trình Before/After & Công Cụ Y Khoa trên {lib_path}...")
    tax_mgr = TaxonomyManager()
    active_proj = tax_mgr.get_active_project()
    domain = active_proj.get("domain", "dermatology_spa")
    enricher = VisionEnricher(tax_mgr)

    info_dirs = glob.glob(os.path.join(images_dir, "*.info"))
    print(f"Tổng số tư liệu cần xử lý: {len(info_dirs)}")

    # 1. Group info dirs by customer/session date
    session_groups = {}
    for d in info_dirs:
        item_id = os.path.basename(d).replace(".info", "")
        item_meta_file = os.path.join(d, "metadata.json")
        if not os.path.exists(item_meta_file):
            continue
        try:
            with open(item_meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            main_file = None
            for fn in os.listdir(d):
                if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".mp4")):
                    main_file = os.path.join(d, fn)
                    break

            name = meta.get("name", "")
            matched_date = "standalone"
            matched_cust = None
            for date_str, cinfo in CUSTOMER_MAP.items():
                if date_str in name:
                    matched_date = date_str
                    matched_cust = cinfo
                    break

            entry = {
                "id": item_id,
                "dir": d,
                "meta_file": item_meta_file,
                "meta": meta,
                "image_path": main_file,
                "name": name,
                "matched_cust": matched_cust,
                "date_str": matched_date if matched_date != "standalone" else None
            }
            session_groups.setdefault(matched_date, []).append(entry)
        except Exception:
            continue

    # 2. Process each session with temporal JourneyClassifier, QualityScorer, and ToolDetector
    updated_items = {}
    now_ms = int(time.time() * 1000)
    customer_counts = {}
    star_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    phase_distribution = {"before": 0, "inprocess": 0, "after": 0}

    for session_date, items_in_session in session_groups.items():
        # Apply Temporal Journey Classification across session
        classified_items = JourneyClassifier.classify_session_items(items_in_session, domain=domain)

        for item in classified_items:
            item_id = item["id"]
            meta = item["meta"]
            name = item["name"]
            matched_cust = item["matched_cust"]
            img_path = item["image_path"]
            phase = item.get("journey_phase", "inprocess")
            phase_distribution[phase] = phase_distribution.get(phase, 0) + 1

            # 2a. Quality Evaluation (1 - 5 Stars)
            q_res = QualityScorer.evaluate_image(img_path)
            rating = q_res["rating"]
            star_distribution[rating] = star_distribution.get(rating, 0) + 1

            # 2b. Domain Technique & Tool Detection
            tool_tags = ToolDetector.detect_techniques(img_path, domain=domain)

            # 2c. Generate comprehensive Marketing & Video Brief
            brief = enricher.generate_brief(
                asset_label=name,
                kind="video" if "video" in name.lower() or meta.get("ext") == "mp4" else "photo",
                customer_name=matched_cust["name"] if matched_cust else None,
                photo_url=meta.get("url"),
                date_str=item.get("date_str"),
                journey_phase=phase,
                quality_info=q_res,
                tool_tags=tool_tags
            )

            # Preserve existing functional folder or determine from brief
            existing_functional_fid = next((fid for fid in meta.get("folders", []) if fid in FOLDERS.values()), None)
            main_fid = existing_functional_fid or FOLDERS.get(brief["pillar_id"], FOLDERS["treatment"])
            folders = [main_fid]

            # Merge all tags cleanly
            current_tags = set(meta.get("tags", []))
            for t in brief["tags"]:
                current_tags.add(t)

            if matched_cust:
                folders.append(matched_cust["folder_id"])
                current_tags.add(matched_cust["tag"])
                customer_counts[matched_cust["name"]] = customer_counts.get(matched_cust["name"], 0) + 1

            tags = sorted(list(current_tags))
            anno = brief["annotation"]
            clean_title = brief["title"]

            meta["name"] = clean_title
            meta["folders"] = folders
            meta["tags"] = tags
            meta["annotation"] = anno
            meta["star"] = rating
            meta["modificationTime"] = now_ms
            meta["lastModified"] = now_ms

            # Save on disk
            with open(item["meta_file"], "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            updated_items[item_id] = meta

            # Update Eagle memory via API
            try:
                payload = json.dumps({
                    "id": item_id,
                    "tags": tags,
                    "annotation": anno,
                    "star": rating
                }).encode("utf-8")
                req = urllib.request.Request("http://localhost:41595/api/item/update", data=payload, headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass

    print(f"\n✅ Đã phân loại chuyên sâu thành công {len(updated_items)} tư liệu!")
    print("\n⭐ Phân bổ Đánh giá Chất lượng (Star Rating):")
    for s in [5, 4, 3, 2, 1]:
        print(f"  {'⭐' * s} ({s} Sao): {star_distribution[s]} tư liệu")

    print("\n⏳ Phân bổ Tiến trình Khách hàng (Temporal Journey):")
    print(f"  🎬 Giai đoạn Trước (Before): {phase_distribution.get('before', 0)} tư liệu")
    print(f"  💆‍♀️ Giai đoạn Thực hiện (In-Process): {phase_distribution.get('inprocess', 0)} tư liệu")
    print(f"  💬 Giai đoạn Kết quả (After): {phase_distribution.get('after', 0)} tư liệu")

    print("\n👤 Khách hàng tiêu biểu:")
    for cname, count in sorted(customer_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  👤 {cname}: {count} tư liệu")

    # 3. Update Eagle persistent cache file (library-caches)
    if os.path.exists(CACHE_FILE):
        print(f"\nĐang cập nhật trực tiếp vào file cache Eagle ({CACHE_FILE})...")
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_items = [json.loads(line) for line in f if line.strip()]

            for it in cache_items:
                iid = it.get("id")
                if iid in updated_items:
                    it["folders"] = updated_items[iid]["folders"]
                    it["tags"] = updated_items[iid]["tags"]
                    it["annotation"] = updated_items[iid]["annotation"]
                    it["star"] = updated_items[iid]["star"]
                    it["lastModified"] = now_ms

            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                for it in cache_items:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
            print("✅ Đã ghi cache Eagle thành công!")
        except Exception as e:
            print("⚠️ Lỗi ghi cache:", e)

    # 4. Trigger Eagle reload
    print("\nĐang gửi lệnh yêu cầu Eagle làm mới lại thư viện...")
    reload_status = "skipped"
    try:
        payload = json.dumps({"libraryPath": lib_path}).encode("utf-8")
        req = urllib.request.Request("http://localhost:41595/api/library/switch", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        res = urllib.request.urlopen(req, timeout=5)
        reload_status = "success"
        print("✅ Eagle reload thành công:", res.read().decode())
    except Exception as e:
        reload_status = f"error: {e}"
        print("⚠️ Lỗi reload Eagle:", e)

    return {
        "status": "completed",
        "total_processed": len(updated_items),
        "star_distribution": star_distribution,
        "phase_distribution": phase_distribution,
        "customer_counts": customer_counts,
        "library_path": lib_path,
        "active_project": active_proj.get("name"),
        "reload_status": reload_status
    }


if __name__ == "__main__":
    run()
