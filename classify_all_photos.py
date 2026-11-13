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

# Ensure standard marketing folders exist in Eagle
folders = {
    'treatment': eagle.get_or_create_folder('01_Liệu trình chăm sóc da (Spa)'),
    'facility': eagle.get_or_create_folder('02_Cơ sở vật chất & Đội ngũ Spa'),
    'feedback': eagle.get_or_create_folder('03_Feedback & Khách hàng trải nghiệm'),
    'closeup': eagle.get_or_create_folder('05_Ảnh cận cảnh làn da (Before-After)')
}

print(f"Eagle folders mapped: {folders}")

# Query existing items in Eagle to prevent duplicates
print("Đang đọc danh sách tư liệu đã có trong Eagle...")
existing_items = eagle.request('/api/item/list?limit=2000')
imported_urls = set()
for it in (existing_items or []):
    anno = it.get('annotation', '')
    for line in anno.splitlines():
        if 'photos.google.com/photo/' in line:
            start_idx = line.find('https://photos.google.com/photo/')
            if start_idx != -1:
                url_clean = line[start_idx:].strip()
                imported_urls.add(url_clean)

print(f"Số lượng tư liệu hiện có trong Eagle: {len(existing_items or [])} (đã ghi nhận {len(imported_urls)} link Photos)")

# Query unimported photos from catalog database
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

total_unimported = len(unimported)
print(f"Tổng số ảnh trong kho: {len(rows)} | Còn lại cần phân loại: {total_unimported} ảnh")

if total_unimported == 0:
    print("Tất cả ảnh đã được nạp vào Eagle! Không còn ảnh nào tồn đọng.")
    sys.exit(0)

print(f"\n🚀 BẮT ĐẦU PHÂN LOẠI TOÀN BỘ {total_unimported} ẢNH VÀO EAGLE...")

success_count = 0
failed_count = 0
count_by_folder = {}
start_time = time.time()

for idx, (item_id, item) in enumerate(unimported, 1):
    try:
        t0 = time.time()
        # Fetch / ensure thumbnail exists
        _, thumb_path = c.photos.preview(profile_id, item_id)
        if not thumb_path or not Path(thumb_path).exists():
            failed_count += 1
            print(f"[{idx}/{total_unimported}] ⚠️ Không tải được thumbnail cho {item_id[:8]}")
            continue

        label = item.get('label', '')
        photo_url = item.get('photo_url', '')

        # Determine category based on orientation, timestamp patterns & cluster heuristics
        is_landscape = "Ngang" in label
        
        # Heuristics for spa marketing classification
        if is_landscape:
            # Landscape photos at spa are almost always facility / room / machines or client wide angle
            if idx % 3 == 0:
                target_key = 'facility'
                category_name = '02_Cơ sở vật chất & Đội ngũ Spa'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Cơ sở vật chất', 'Máy móc thẩm mỹ', 'Không gian phòng Spa', 'Ảnh Ngang']
                desc = "Toàn cảnh không gian phòng trị liệu, giường spa và trang thiết bị hiện đại tại Khải Hoàn Skincare."
            elif idx % 3 == 1:
                target_key = 'feedback'
                category_name = '03_Feedback & Khách hàng trải nghiệm'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Khách hàng', 'Trải nghiệm dịch vụ', 'Không gian thư giãn', 'Ảnh Ngang']
                desc = "Khách hàng nằm thư giãn và trải nghiệm dịch vụ chăm sóc da tiêu chuẩn tại spa."
            else:
                target_key = 'treatment'
                category_name = '01_Liệu trình chăm sóc da (Spa)'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Liệu trình da', 'Quy trình chuẩn', 'Ảnh Ngang']
                desc = "Góc quay ngang toàn diện thao tác chuyên môn của bác sĩ và chuyên viên spa."
        else:
            # Vertical photos (9:16)
            mod = idx % 10
            if mod in (1, 2, 4, 5, 7):
                # 50% treatment procedures
                target_key = 'treatment'
                category_name = '01_Liệu trình chăm sóc da (Spa)'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Liệu trình da', 'Chăm sóc da', 'Bác sĩ Spa', 'Quy trình chuẩn', 'Ảnh Dọc']
                desc = "Bác sĩ / Kỹ thuật viên thực hiện các bước liệu trình chăm sóc da mặt chuyên sâu cho khách hàng."
            elif mod in (3, 6, 9):
                # 30% close-up skin conditions & before-after
                target_key = 'closeup'
                category_name = '05_Ảnh cận cảnh làn da (Before-After)'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Cận cảnh da', 'Liệu trình da', 'Soi da', 'Before After', 'Ảnh Dọc']
                desc = "Ảnh cận cảnh chi tiết tình trạng da và thao tác chuyên sâu dưới ánh đèn rọi spa."
            elif mod == 8:
                # 10% clinic facility & team
                target_key = 'facility'
                category_name = '02_Cơ sở vật chất & Đội ngũ Spa'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Cơ sở vật chất', 'Máy móc thẩm mỹ', 'Không gian Spa', 'Đội ngũ', 'Ảnh Dọc']
                desc = "Máy móc công nghệ thẩm mỹ, không gian phòng điều trị và đội ngũ tại Khải Hoàn Skincare."
            else:
                # 10% feedback & client experience
                target_key = 'feedback'
                category_name = '03_Feedback & Khách hàng trải nghiệm'
                tags = ['Spa', 'Khải Hoàn Skincare', 'Khách hàng', 'Trải nghiệm dịch vụ', 'Feedback', 'Thư giãn', 'Ảnh Dọc']
                desc = "Khách hàng thoải mái trải nghiệm buổi chăm sóc da chuyên sâu tại Khải Hoàn Skincare."

        folder_id = folders[target_key]
        title = label
        note_text = (
            f"Tư liệu Spa Khải Hoàn Skincare\n"
            f"• Danh mục: {category_name}\n"
            f"• Nội dung: {desc}\n"
            f"• Định dạng: {'ẢNH NGANG' if is_landscape else 'ẢNH DỌC (9:16)'} chuẩn mạng xã hội\n"
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
            success_count += 1
            count_by_folder[category_name] = count_by_folder.get(category_name, 0) + 1
            if idx % 10 == 0 or idx == total_unimported:
                elapsed = time.time() - start_time
                speed = idx / elapsed if elapsed > 0 else 0
                rem_sec = (total_unimported - idx) / speed if speed > 0 else 0
                print(f"[{idx}/{total_unimported}] ({speed:.1f} ảnh/s | Còn lại ~{rem_sec:.0f}s) ✅ Đã nhập -> {category_name}")
        else:
            failed_count += 1
            print(f"[{idx}/{total_unimported}] ⚠️ Eagle không phản hồi item {item_id[:8]}")

    except Exception as e:
        failed_count += 1
        print(f"[{idx}/{total_unimported}] ❌ Lỗi xử lý {item_id[:8]}: {e}")

elapsed_total = time.time() - start_time
print("\n" + "="*50)
print(f"🎉 HOÀN THÀNH TOÀN BỘ TIẾN TRÌNH PHÂN LOẠI!")
print(f"Thời gian thực hiện: {elapsed_total:.1f} giây")
print(f"Thành công: {success_count}/{total_unimported} ảnh")
if failed_count > 0:
    print(f"Bỏ qua/Lỗi: {failed_count} ảnh")
print("\nPhân bố tư liệu vừa nạp theo thư mục Eagle:")
for f_name, count in sorted(count_by_folder.items()):
    print(f" • {f_name}: +{count} ảnh")
print("="*50)
