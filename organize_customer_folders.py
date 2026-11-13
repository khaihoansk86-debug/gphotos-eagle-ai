import os
import sys
import json
import glob
import time
import urllib.request
import sqlite3

LIBRARY_PATH = r"D:\test.library"
META_PATH = os.path.join(LIBRARY_PATH, "metadata.json")
MTIME_PATH = os.path.join(LIBRARY_PATH, "mtime.json")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def eagle_api(path, payload=None):
    url = f"http://localhost:41595{path}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    else:
        req = urllib.request.Request(url)
    res = urllib.request.urlopen(req, timeout=10)
    return json.loads(res.read().decode())

def get_or_create_folder(folder_name, parent_id=None):
    # Search existing folders
    existing = eagle_api("/api/folder/list").get("data", [])
    
    def find_node(nodes):
        for n in nodes:
            if n.get("name") == folder_name:
                return n.get("id")
            sub = n.get("children", [])
            if sub:
                f_id = find_node(sub)
                if f_id:
                    return f_id
        return None

    found = find_node(existing)
    if found:
        return found
        
    payload = {"folderName": folder_name}
    if parent_id:
        payload["parent"] = parent_id
    res = eagle_api("/api/folder/create", payload)
    return res.get("data", {}).get("id")

def setup_folders():
    print("🚀 Bắt đầu thiết lập cấu trúc thư mục tối ưu trong Eagle...")
    
    # 1. Main functional folders
    spa_folder_id = get_or_create_folder("01_Hình ảnh về Spa (Cơ sở vật chất, Máy móc, Không gian)")
    feedback_folder_id = get_or_create_folder("02_Feedback Khách Hàng (Soi gương, Thư giãn sau điều trị)")
    hook_folder_id = get_or_create_folder("03_Hook 3s TikTok (Cận cảnh da mụn, Nặn mụn, Soi da)")
    treatment_folder_id = get_or_create_folder("04_B-Roll Liệu trình & Thao tác Bác sĩ - KTV (Quy trình chuẩn)")
    video_folder_id = get_or_create_folder("05_Raw Video Footage (CapCut Reels - TikTok Dọc)")
    
    # 2. Main customer folder
    cust_parent_id = get_or_create_folder("06_Hồ sơ Khách Hàng (Case Studies & Feedback)")
    
    # 3. Read top 20 customer albums from SQLite
    db = sqlite3.connect(os.path.join(BASE_DIR, "v2", "data", "catalog.sqlite"))
    cursor = db.execute("SELECT title, item_count FROM photos_albums ORDER BY item_count DESC LIMIT 20")
    top_albums = cursor.fetchall()
    
    customer_folders = {}
    for idx, (title, count) in enumerate(top_albums, 1):
        f_name = f"{idx:02d}_{title} ({count} tư liệu)"
        c_id = get_or_create_folder(f_name, parent_id=cust_parent_id)
        customer_folders[title] = {
            "id": c_id,
            "name": f_name,
            "short_name": title.split("-")[0].strip(),
            "tag": f"Khách_{title.split('-')[0].strip().replace(' ', '_')}"
        }
        print(f"  📁 Đã tạo thư mục khách: {f_name}")
        
    print(f"✅ Đã tạo thành công {len(customer_folders)} thư mục khách hàng trong Eagle!")
    
    return {
        "spa": spa_folder_id,
        "feedback": feedback_folder_id,
        "hook": hook_folder_id,
        "treatment": treatment_folder_id,
        "video": video_folder_id,
        "customer_parent": cust_parent_id,
        "customers": customer_folders
    }

def map_and_update_items(folder_map):
    images_dir = os.path.join(LIBRARY_PATH, "images")
    info_dirs = glob.glob(os.path.join(images_dir, "*.info"))
    print(f"\nBắt đầu cập nhật phân loại cho {len(info_dirs)} tư liệu...")
    
    # Map top date sessions to customer folders
    # Top dates in catalog:
    date_to_customer = {
        "12 thg 11, 2026": "Thu Lee - 0967033270",
        "3 thg 10, 2026": "Chị Ngọc",
        "23 thg 10, 2026": "Nguyễn Thị Kim Ngân 0987601974",
        "28 thg 10, 2026": "Chị Phương b c Ngọc",
        "25 thg 9, 2026": "Ng T Xinh",
        "10 thg 10, 2026": "Phan Thị Hạnh",
        "26 thg 10, 2026": "Châu Thị Ngọc Thúy - 0944840188",
        "2 thg 10, 2026": "Ngô Phương - 0937024555",
        "7 thg 10, 2026": "Xuân Hương",
        "5 thg 11, 2026": "Lê Ng Hồng Nhung 0393439625",
        "20 thg 9, 2026": "Phan T Kim Oanh 0937370664",
        "22 thg 10, 2026": "Ngô Thị Út 0387494003",
        "8 thg 11, 2026": "Trần T Thanh Nhàn 0334412337 (stt 289)",
        "6 thg 10, 2026": "Nguyễn Thị Thanh Tuyền 0938049398 ( cô c thảo )",
        "12 thg 10, 2026": "Bùi Thái Quỳnh Thi 0912503340",
        "9 thg 10, 2026": "Võ T Thanh Tuyền cf muối",
        "29 thg 10, 2026": "Võ Thành Ý 0901666827",
        "17 thg 10, 2026": "Trần Thị Nhã Linh-0944280229(stt 300)",
        "24 thg 10, 2026": "Nguyễn Hoàng Phi 0911486119",
        "11 thg 10, 2026": "Lê Thị Hồng Hoa 0869223630"
    }

    now_ms = int(time.time() * 1000)
    updated_items = 0
    mtimes = {}
    if os.path.exists(MTIME_PATH):
        try:
            with open(MTIME_PATH, "r", encoding="utf-8") as f:
                mtimes = json.load(f)
        except Exception:
            mtimes = {}

    for idx, d in enumerate(info_dirs, 1):
        item_id = os.path.basename(d).replace(".info", "")
        item_meta_file = os.path.join(d, "metadata.json")
        if not os.path.exists(item_meta_file):
            continue
            
        with open(item_meta_file, "r", encoding="utf-8") as f:
            item_meta = json.load(f)
            
        clean_name = item_meta.get("name", "")
        
        # Determine functional category
        anno = item_meta.get("annotation", "")
        if "05_Raw Video Footage" in anno or "Video" in clean_name:
            main_folder_id = folder_map["video"]
            cat_name = "05_Raw Video Footage"
        elif "04_Cơ sở vật chất" in anno:
            main_folder_id = folder_map["spa"]
            cat_name = "01_Hình ảnh về Spa (Cơ sở, Máy móc, Không gian)"
        elif "03_Feedback" in anno:
            main_folder_id = folder_map["feedback"]
            cat_name = "02_Feedback Khách Hàng (Soi gương, Thư giãn)"
        elif "01_Hook 3s" in anno:
            main_folder_id = folder_map["hook"]
            cat_name = "03_Hook 3s TikTok (Cận cảnh da mụn, Nặn mụn)"
        else:
            main_folder_id = folder_map["treatment"]
            cat_name = "04_B-Roll Liệu trình & Thao tác Bác sĩ - KTV"

        # Determine Customer assignment based on date
        assigned_cust_title = None
        for date_str, cust_title in date_to_customer.items():
            if date_str in clean_name:
                assigned_cust_title = cust_title
                break
                
        folders_list = [main_folder_id]
        tags = item_meta.get("tags", [])
        
        if assigned_cust_title and assigned_cust_title in folder_map["customers"]:
            cust_info = folder_map["customers"][assigned_cust_title]
            folders_list.append(cust_info["id"])
            if cust_info["tag"] not in tags:
                tags.append(cust_info["tag"])
            # Update annotation with customer header
            if "Khách hàng:" not in anno:
                anno = f"👤 Khách hàng: {assigned_cust_title}\n" + anno
                
        item_meta["folders"] = folders_list
        item_meta["tags"] = tags
        item_meta["annotation"] = anno
        item_meta["modificationTime"] = now_ms
        item_meta["lastModified"] = now_ms
        
        with open(item_meta_file, "w", encoding="utf-8") as f:
            json.dump(item_meta, f, ensure_ascii=False, indent=2)
            
        mtimes[item_id] = now_ms
        updated_items += 1
        
        # Also update live via Eagle API so UI is refreshed in memory
        try:
            eagle_api("/api/item/update", {
                "id": item_id,
                "tags": tags,
                "annotation": anno
            })
        except Exception:
            pass

    with open(MTIME_PATH, "w", encoding="utf-8") as f:
        json.dump(mtimes, f)
        
    print(f"🎉 Đã cập nhật xong {updated_items} tư liệu vào các thư mục Khách Hàng và Chức Năng!")
    
    # Reload Eagle Library
    print("\nĐang gửi lệnh yêu cầu Eagle làm mới lại toàn bộ thư mục từ đĩa...")
    try:
        res = eagle_api("/api/library/switch", {"libraryPath": LIBRARY_PATH})
        print("✅ Eagle đã reload thành công:", res)
    except Exception as e:
        print("⚠️ Lỗi gọi Eagle switch:", e)

if __name__ == "__main__":
    fmap = setup_folders()
    map_and_update_items(fmap)
