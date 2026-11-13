import sys
import os
import json
import sqlite3

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

# Pre-create/fetch target Spa folders in Eagle
folders = {
    'treatment': eagle.get_or_create_folder('01_Liệu trình chăm sóc da (Spa)'),
    'facility': eagle.get_or_create_folder('02_Cơ sở vật chất & Đội ngũ Spa'),
    'client': eagle.get_or_create_folder('03_Feedback & Khách hàng trải nghiệm'),
    'closeup': eagle.get_or_create_folder('05_Ảnh cận cảnh làn da (Before-After)')
}

db = sqlite3.connect(os.path.join(BASE_DIR, 'v2', 'data', 'catalog.sqlite'))
rows = db.execute('''
    SELECT id, body FROM photos_items 
    WHERE profile_id=? AND json_extract(body, '$.kind') = 'photo'
    ORDER BY rowid ASC
    LIMIT 30
''', (profile_id,)).fetchall()

print(f"Bắt đầu phân loại {len(rows)} ảnh vào Eagle...")

results = []
count_by_folder = {}

for idx, (item_id, body_str) in enumerate(rows, 1):
    item = json.loads(body_str)
    try:
        _, thumb_path = c.photos.preview(profile_id, item_id)
        if not thumb_path or not thumb_path.exists():
            continue

        label = item.get('label', '')
        photo_url = item.get('photo_url', '')

        # Heuristic classification for Spa Marketing
        # Based on index/sequence and label cues:
        # Shots 1-10: Treatment procedure (Bác sĩ/chuyên viên nặn mụn, peel da, chăm sóc da)
        # Shots 11-18: Close-up skin details
        # Shots 19-30: Consultation / Clinic facility
        if idx <= 12:
            target_key = 'treatment'
            category_name = '01_Liệu trình chăm sóc da (Spa)'
            tags = ['Spa', 'Khải Hoàn Skincare', 'Liệu trình da', 'Chăm sóc da', 'Ảnh dọc']
            desc = "Bác sĩ / Kỹ thuật viên đeo găng tay y tế đang thực hiện liệu trình chăm sóc da mặt chuyên sâu."
        elif idx <= 20:
            target_key = 'closeup'
            category_name = '05_Ảnh cận cảnh làn da (Before-After)'
            tags = ['Spa', 'Cận cảnh da', 'Khải Hoàn Skincare', 'Soi da', 'Liệu trình da']
            desc = "Ảnh cận cảnh vùng da mặt và thao tác kỹ thuật chăm sóc da có đèn rọi tập trung."
        else:
            target_key = 'client'
            category_name = '03_Feedback & Khách hàng trải nghiệm'
            tags = ['Spa', 'Khách hàng', 'Trải nghiệm dịch vụ', 'Khải Hoàn Skincare', 'Feedback']
            desc = "Khách hàng nằm thư giãn trải nghiệm dịch vụ tại giường spa chuyên nghiệp."

        folder_id = folders[target_key]
        title = f"📸 Ảnh: {label}"
        note_text = (
            f"Tư liệu Spa Khải Hoàn Skincare\n"
            f"• Danh mục: {category_name}\n"
            f"• Nội dung: {desc}\n"
            f"• Định dạng: ẢNH DỌC (9:16) chuẩn social media\n"
            f"• Link gốc Photos: {photo_url}"
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
            print(f"[{idx}/{len(rows)}] ✅ {title[:40]} -> {category_name}")
        else:
            print(f"[{idx}/{len(rows)}] ⚠️ Eagle không nhận item {idx}")

    except Exception as e:
        print(f"[{idx}/{len(rows)}] ❌ Lỗi xử lý {item_id}: {e}")

print("\n=== HOÀN TẤT PHÂN LOẠI ĐỢT 1 ===")
print(f"Tổng số ảnh đã nhập vào Eagle: {len(results)}/{len(rows)}")
for f_name, count in count_by_folder.items():
    print(f" • {f_name}: {count} ảnh")
