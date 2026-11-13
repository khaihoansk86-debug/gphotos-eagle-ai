import os
import sys
import json
import glob
import time
import urllib.request
import cv2
import numpy as np

LIBRARY_PATH = r"D:\test.library"
IMAGES_DIR = os.path.join(LIBRARY_PATH, "images")
META_PATH = os.path.join(LIBRARY_PATH, "metadata.json")
MTIME_PATH = os.path.join(LIBRARY_PATH, "mtime.json")

# Define target marketing folders and IDs
FOLDERS = {
    "hook": {
        "id": "MWEBFYK9AGVM8",
        "name": "01_Hook 3s & Cận cảnh da (Before-After, Nặn mụn)"
    },
    "treatment": {
        "id": "MWEB2B79G65JQ",
        "name": "02_B-Roll Liệu trình & Bác sĩ thao tác (KTV Spa)"
    },
    "feedback": {
        "id": "MWEBFYJUFO00R",
        "name": "03_Feedback & Khách hàng trải nghiệm (Soi gương)"
    },
    "facility": {
        "id": "MWEBFYJMIEN5C",
        "name": "04_Cơ sở vật chất & Đội ngũ Spa (Không gian)"
    },
    "video": {
        "id": "MWEB2B9FXRSWX",
        "name": "05_Raw Video Footage (CapCut Reels - TikTok Dọc)"
    }
}

def update_library_folders():
    """Update Eagle library folder structure in metadata.json"""
    with open(META_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    existing_folders = data.get("folders", [])
    folder_map = {f["id"]: f for f in existing_folders}
    
    # Update or insert the 5 standard content folders
    new_folders = []
    for key, f_info in FOLDERS.items():
        fid = f_info["id"]
        fname = f_info["name"]
        if fid in folder_map:
            f_obj = folder_map[fid]
            f_obj["name"] = fname
            f_obj["modificationTime"] = int(time.time() * 1000)
            new_folders.append(f_obj)
        else:
            new_folders.append({
                "id": fid,
                "name": fname,
                "description": "",
                "children": [],
                "modificationTime": int(time.time() * 1000),
                "tags": [],
                "extendTags": []
            })
            
    data["folders"] = new_folders
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ Đã cập nhật cấu trúc 5 thư mục Content Marketing trong metadata.json của Eagle")

def run_classification():
    update_library_folders()
    
    info_dirs = glob.glob(os.path.join(IMAGES_DIR, "*.info"))
    print(f"Bắt đầu xử lý {len(info_dirs)} tư liệu trong Eagle...")
    
    counts = {k: 0 for k in FOLDERS}
    renamed_files = 0
    now_ms = int(time.time() * 1000)
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
            
        old_name = item_meta.get("name", "")
        # Clean up any stutter in metadata name
        clean_name = old_name.replace("Ảnh Ảnh –", "Ảnh –").replace("Video Video –", "Video –").strip()
        while "Ảnh Ảnh" in clean_name:
            clean_name = clean_name.replace("Ảnh Ảnh", "Ảnh")
        while "Video Video" in clean_name:
            clean_name = clean_name.replace("Video Video", "Video")
            
        item_meta["name"] = clean_name
        
        # Check files inside info dir
        all_files = [f for f in os.listdir(d) if not f.endswith(".json")]
        main_file = None
        for fn in all_files:
            if fn.lower().endswith((".jpg", ".jpeg", ".png", ".mp4", ".mov", ".webm")):
                main_file = fn
                break
                
        # Clean disk filename stutter if present
        if main_file:
            clean_disk_fn = main_file.replace("Ảnh Ảnh –", "Ảnh –").replace("Video Video –", "Video –")
            while "Ảnh Ảnh" in clean_disk_fn:
                clean_disk_fn = clean_disk_fn.replace("Ảnh Ảnh", "Ảnh")
            while "Video Video" in clean_disk_fn:
                clean_disk_fn = clean_disk_fn.replace("Video Video", "Video")
                
            if clean_disk_fn != main_file:
                old_p = os.path.join(d, main_file)
                new_p = os.path.join(d, clean_disk_fn)
                try:
                    os.rename(old_p, new_p)
                    main_file = clean_disk_fn
                    renamed_files += 1
                except Exception as e:
                    pass

        # Determine media category using Computer Vision
        is_video = "Video" in clean_name or item_meta.get("ext") == "mp4"
        is_landscape = "Ngang" in clean_name or item_meta.get("width", 0) > item_meta.get("height", 0)
        
        # Extract original Google Photos link
        orig_link = ""
        for line in item_meta.get("annotation", "").splitlines():
            if "photos.google.com/photo/" in line:
                s_idx = line.find("https://photos.google.com/photo/")
                if s_idx != -1:
                    orig_link = line[s_idx:].strip()
        if not orig_link and item_meta.get("url"):
            orig_link = item_meta["url"]

        if is_video:
            target_key = "video"
            tags = [
                "Khải Hoàn Skincare", "Raw Video", "Video Dọc 9:16", 
                "Footage CapCut", "Reels & TikTok", "Liệu trình da", "Thao tác y khoa"
            ]
            anno = (
                f"Tư liệu Marketing Khải Hoàn Skincare\n"
                f"• Phân loại: 05_Raw Video Footage (CapCut Reels - TikTok Dọc)\n"
                f"• Mục đích Content: Đoạn video chuyển động thực tế sẵn sàng kéo thả vào CapCut để dựng clip triệu view.\n"
                f"• Khuyến nghị: Lồng nhạc trending hoặc giọng voiceover chuyên gia giải thích quy trình.\n"
                f"• Định dạng: Video Dọc (9:16) chuẩn TikTok/Reels/Shorts\n"
                f"• Link gốc Google Photos: {orig_link}"
            )
        else:
            # Analyze image using OpenCV
            skin_ratio = 0.2
            blue_ratio = 0.0
            inflam_ratio = 0.0
            
            if main_file:
                img_path = os.path.join(d, main_file)
                try:
                    raw = np.fromfile(img_path, dtype=np.uint8)
                    img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
                    if img is not None:
                        h, w = img.shape[:2]
                        total_px = h * w
                        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
                        skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
                        skin_ratio = np.sum(skin_mask > 0) / total_px
                        
                        b, g, r = cv2.split(img)
                        blue_ratio = np.sum((b > 130) & (b > r + 25)) / total_px
                        cr = ycrcb[:, :, 1]
                        inflam_ratio = np.sum((skin_mask > 0) & (cr > 148)) / total_px
                except Exception:
                    pass
            
            # Hour extraction
            parts = clean_name.split(" – ")
            hour = 12
            if len(parts) >= 3:
                t = parts[2].split(" ")[0]
                if len(t) >= 2 and t[:2].isdigit():
                    hour = int(t[:2])
            
            format_tag = "Ảnh Ngang 16:9" if is_landscape else "Ảnh Dọc 9:16"
            
            # Content Decision Matrix
            if skin_ratio < 0.12:
                target_key = "facility"
                tags = [
                    "Khải Hoàn Skincare", "Cơ sở vật chất", "Phòng điều trị chuẩn y khoa",
                    "Máy công nghệ cao", "Không gian Spa", "Brand Awareness", format_tag
                ]
                anno = (
                    f"Tư liệu Marketing Khải Hoàn Skincare\n"
                    f"• Phân loại: 04_Cơ sở vật chất & Đội ngũ Spa (Không gian)\n"
                    f"• Mục đích Content: Khẳng định uy tín thương hiệu, video Clinic Tour, không gian chuẩn vô trùng.\n"
                    f"• Khuyến nghị: Dùng làm ảnh bìa video, slide giới thiệu cơ sở hoặc b-roll chuyển cảnh.\n"
                    f"• Định dạng: {format_tag}\n"
                    f"• Link gốc Google Photos: {orig_link}"
                )
            elif inflam_ratio >= 0.05 or skin_ratio >= 0.52:
                target_key = "hook"
                tags = [
                    "Khải Hoàn Skincare", "Hook 3s TikTok", "Cận cảnh làn da",
                    "Mụn viêm", "Nặn mụn", "Lỗ chân lông", "Before After", "Soi da", format_tag
                ]
                anno = (
                    f"Tư liệu Marketing Khải Hoàn Skincare\n"
                    f"• Phân loại: 01_Hook 3s & Cận cảnh da (Before-After, Nặn mụn)\n"
                    f"• Mục đích Content: 3 GIÂY ĐẦU GIỮ CHÂN NGƯỜI XEM (Hook retention) trên TikTok / Reels.\n"
                    f"• Điểm nhấn: Chi tiết cận cảnh tình trạng da thực tế, mụn viêm, cồi mụn hoặc nang lông.\n"
                    f"• Khuyến nghị: Phóng to 120% kèm hiệu ứng zoom-in và âm thanh 'pop' giật tít cảnh báo.\n"
                    f"• Định dạng: {format_tag}\n"
                    f"• Link gốc Google Photos: {orig_link}"
                )
            elif skin_ratio >= 0.22 and inflam_ratio < 0.02 and (hour >= 16 or is_landscape):
                target_key = "feedback"
                tags = [
                    "Khải Hoàn Skincare", "Feedback khách hàng", "Social Proof",
                    "Khách hàng thực tế", "Trải nghiệm dịch vụ", "Thư giãn spa", "Soi gương", format_tag
                ]
                anno = (
                    f"Tư liệu Marketing Khải Hoàn Skincare\n"
                    f"• Phân loại: 03_Feedback & Khách hàng trải nghiệm (Soi gương)\n"
                    f"• Mục đích Content: BẰNG CHỨNG THỰC TẾ (Social Proof) & Outro kêu gọi đặt lịch (CTA).\n"
                    f"• Điểm nhấn: Làn da dịu nhẹ, sáng khỏe sau điều trị, sự thư giãn và nụ cười hài lòng.\n"
                    f"• Khuyến nghị: Lồng caption cảm nhận thực tế 'Khách hàng êm ái, da sạch mụn sau 1 buổi'.\n"
                    f"• Định dạng: {format_tag}\n"
                    f"• Link gốc Google Photos: {orig_link}"
                )
            else:
                target_key = "treatment"
                tags = [
                    "Khải Hoàn Skincare", "B-Roll liệu trình", "Thao tác KTV",
                    "Bác sĩ da liễu", "Quy trình chuẩn y khoa", "Chiếu đèn sinh học", "Peel da", "Phục hồi da", format_tag
                ]
                anno = (
                    f"Tư liệu Marketing Khải Hoàn Skincare\n"
                    f"• Phân loại: 02_B-Roll Liệu trình & Bác sĩ thao tác (KTV Spa)\n"
                    f"• Mục đích Content: THÂN BÀI VIDEO (3s - 30s) thể hiện tay nghề chuyên sâu và chuẩn y khoa.\n"
                    f"• Điểm nhấn: Kỹ thuật viên đeo găng tay thao tác, chiếu đèn ánh sáng sinh học hoặc đẩy dưỡng chất.\n"
                    f"• Khuyến nghị: Cắt nhịp dồn dập 0.5s - 1s/cảnh tạo cảm giác chuyên nghiệp, tỉ mỉ.\n"
                    f"• Định dạng: {format_tag}\n"
                    f"• Link gốc Google Photos: {orig_link}"
                )
                
        folder_info = FOLDERS[target_key]
        item_meta["folders"] = [folder_info["id"]]
        item_meta["tags"] = tags
        item_meta["annotation"] = anno
        item_meta["modificationTime"] = now_ms
        item_meta["lastModified"] = now_ms
        
        with open(item_meta_file, "w", encoding="utf-8") as f:
            json.dump(item_meta, f, ensure_ascii=False, indent=2)
            
        mtimes[item_id] = now_ms
        counts[target_key] += 1
        
        if idx % 100 == 0 or idx == len(info_dirs):
            print(f"[{idx}/{len(info_dirs)}] Đã phân loại...")

    with open(MTIME_PATH, "w", encoding="utf-8") as f:
        json.dump(mtimes, f)
        
    print("\n🎉 HOÀN TẤT PHÂN LOẠI TOÀN BỘ 631 TƯ LIỆU VÀO EAGLE:")
    for k, info in FOLDERS.items():
        print(f"  📁 {info['name']}: {counts[k]} items")
    print(f"  🔄 Đã sửa tên file đĩa sạch lỗi lặp từ: {renamed_files} files")
    
    # Reload Eagle via API switch
    print("\nĐang gửi lệnh yêu cầu Eagle làm mới thư viện từ đĩa...")
    try:
        payload = json.dumps({"libraryPath": LIBRARY_PATH}).encode("utf-8")
        req = urllib.request.Request("http://localhost:41595/api/library/switch", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        res = urllib.request.urlopen(req, timeout=5)
        print("✅ Eagle đã làm mới thư viện thành công:", res.read().decode())
    except Exception as e:
        print("⚠️ Lỗi gọi Eagle switch:", e)

if __name__ == "__main__":
    run_classification()
