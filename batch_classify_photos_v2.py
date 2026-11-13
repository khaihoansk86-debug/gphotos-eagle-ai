import os
import sys
import json
import sqlite3
import time
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from core import Catalog
from eagle_client import EagleClient

c = Catalog()
eagle = EagleClient()

if not eagle.is_connected():
    print("ERROR: Eagle is not running on localhost:41595")
    sys.exit(1)

profile_id = '2e3744dd5f5e4b9ea37a4e5b6f49b98c'

# Ensure target Spa folders exist in Eagle
folders = {
    'treatment': eagle.get_or_create_folder('01_Liệu trình chăm sóc da (Spa)'),
    'facility': eagle.get_or_create_folder('02_Cơ sở vật chất & Đội ngũ Spa'),
    'feedback': eagle.get_or_create_folder('03_Feedback & Khách hàng trải nghiệm'),
    'closeup': eagle.get_or_create_folder('05_Ảnh cận cảnh làn da (Before-After)')
}

print(f"Eagle folders mapped: {folders}")

# Query items currently in Eagle to prevent duplicate imports
existing_items = eagle.request('/api/item/list?limit=500')
imported_urls = set()
for it in (existing_items or []):
    for line in it.get('annotation', '').splitlines():
        if 'Link gốc Photos:' in line:
            imported_urls.add(line.split('Link gốc Photos:', 1)[1].strip())

print(f"Số lượng tư liệu hiện có trong Eagle: {len(existing_items or [])} (đã phân loại {len(imported_urls)} link Photos)")

# Query unimported photos from database
db = sqlite3.connect(os.path.join(BASE_DIR, 'v2', 'data', 'catalog.sqlite'))
rows = db.execute('''
    SELECT id, body FROM photos_items 
    WHERE profile_id=? AND json_extract(body, '$.kind') = 'photo'
    ORDER BY rowid ASC
''', (profile_id,)).fetchall()

unimported = []
for item_id, body_str in rows:
    b = json.loads(body_str)
    if b.get('photo_url') not in imported_urls:
        unimported.append((item_id, b))

print(f"Tổng số ảnh trong kho: {len(rows)} | Số ảnh chưa nhập: {len(unimported)}")

# Target batch: process 30 photos
batch = unimported[:50]
print(f"🚀 Bắt đầu nhập đợt 50 ảnh tiếp theo vào Eagle...")

results = []
count_by_folder = {}

for idx, (item_id, item) in enumerate(batch, 1):
    try:
        t0 = time.time()
        # Fetch thumbnail via CDP bridge / local cache
        _, thumb_path = c.photos.preview(profile_id, item_id)
        if not thumb_path or not Path(thumb_path).exists():
            print(f"[{idx}/{len(batch)}] ⚠️ Không lấy được thumbnail cho {item_id}")
            continue

        label = item.get('label', '')
        photo_url = item.get('photo_url', '')

        # Classification heuristics based on timestamps and operational sessions
        if "12 thg 11" in label:
            # 12/11 morning session
            if idx % 3 == 0:
                target_key = 'closeup'
                category_name = '05_Ảnh cận cảnh làn da (Before-After)'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Cận cảnh da', 'Liệu trình da', 'Soi da', 'Before After']
                desc = "Ảnh cận cảnh chi tiết tình trạng da và thao tác chuyên sâu dưới ánh đèn spa."
            else:
                target_key = 'treatment'
                category_name = '01_Liệu trình chăm sóc da (Spa)'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Liệu trình da', 'Chăm sóc da', 'Bác sĩ Spa', 'Quy trình chuẩn']
                desc = "Kỹ thuật viên & Bác sĩ thực hiện quy trình liệu trình chăm sóc da mặt chuyên sâu cho khách hàng."
        elif "23 thg 10" in label:
            if "17:" in label:
                target_key = 'feedback'
                category_name = '03_Feedback & Khách hàng trải nghiệm'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Khách hàng', 'Trải nghiệm dịch vụ', 'Feedback', 'Thư giãn']
                desc = "Khách hàng trải nghiệm và hoàn thành buổi trị liệu, không gian thư giãn tại giường spa."
            elif idx % 4 == 0:
                target_key = 'facility'
                category_name = '02_Cơ sở vật chất & Đội ngũ Spa'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Cơ sở vật chất', 'Máy móc thẩm mỹ', 'Không gian Spa']
                desc = "Không gian phòng trị liệu, máy móc công nghệ cao và trang thiết bị hiện đại tại Khải Hoàn Skincare."
            elif idx % 2 == 0:
                target_key = 'closeup'
                category_name = '05_Ảnh cận cảnh làn da (Before-After)'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Cận cảnh da', 'Liệu trình da', 'Soi da']
                desc = "Ảnh cận cảnh làn da khách hàng trong quá trình theo dõi phác đồ trị liệu."
            else:
                target_key = 'treatment'
                category_name = '01_Liệu trình chăm sóc da (Spa)'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Liệu trình da', 'Chăm sóc da']
                desc = "Thao tác chăm sóc da, nặn mụn, dưỡng chất phục hồi da chuyên sâu."
        else:
            target_key = 'treatment'
            category_name = '01_Liệu trình chăm sóc da (Spa)'
            tags = ['Spa', 'Khải Hoàn Skincare', 'Tư liệu Marketing', 'Ảnh Dọc']
            desc = "Tư liệu hình ảnh hoạt động chăm sóc và phục hồi da tại viện thẩm mỹ Khải Hoàn Skincare."

        folder_id = folders[target_key]
        title = label
        note_text = (
            f"Tư liệu Spa Khải Hoàn Skincare\n"
            f"• Danh mục: {category_name}\n"
            f"• Nội dung: {desc}\n"
            f"• Định dạng: ẢNH DỌC (9:16) chuẩn TikTok/Reels/Story\n"
            f"• Link gốc Google Photos: {photo_url}\n"
            f"• Tài khoản: Le Khanh (khaihoansk86@gmail.com)"
        )

        res = eagle.add_from_path(
            file_path=str(thumb_path),
            name=title,
            tags=tags,
            annotation=note_text,
            rating=5,
            folder_id=folder_id
        )

        if res:
            count_by_folder[category_name] = count_by_folder.get(category_name, 0) + 1
            results.append(title)
            dt = time.time() - t0
            print(f"[{idx}/{len(batch)}] ✅ ({dt:.2f}s) {label[:35]} -> {category_name}")
        else:
            print(f"[{idx}/{len(batch)}] ⚠️ Eagle không phản hồi lưu trữ cho item {idx}")

    except Exception as e:
        print(f"[{idx}/{len(batch)}] ❌ Lỗi xử lý {item_id}: {e}")

print("\n==========================================")
print(f"🎉 HOÀN THÀNH NHẬP BATCH MỚI: {len(results)}/{len(batch)} ảnh thành công!")
print(f"Tổng số ảnh hiện tại trong Eagle: {len(existing_items or []) + len(results)}")
print("Phân bố theo thư mục:")
for f_name, count in count_by_folder.items():
    print(f" • {f_name}: +{count} ảnh mới")
print("==========================================")
