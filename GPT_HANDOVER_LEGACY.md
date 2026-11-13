# 📋 TÀI LIỆU BÀN GIAO DỰ ÁN CHO GPT / AI AGENT
## DỰ ÁN: GOOGLE PHOTOS ➔ EAGLE AI BRIDGE (MARKETING DAM AUTOMATION)

> **Dành cho GPT / AI Assistant:** Đây là tài liệu bàn giao kỹ thuật toàn diện để bạn có thể tiếp quản, vận hành, bảo trì hoặc phát triển thêm tính năng cho dự án này ngay lập tức mà không cần hỏi lại người dùng về bối cảnh ban đầu.

---

## 1. Vị Trí Lưu Trữ Dự Án (Project Location)

* **Thư mục dự án chính:**
  * **Trên Windows:** `c:\Users\Admin\Documents\antigravity\amazing-curie\gphotos_eagle_ai\`
  * **Trên macOS:** `~/Documents/antigravity/amazing-curie/gphotos_eagle_ai/` (hoặc thư mục tương đương khi copy sang Mac)
* **Thư mục dữ liệu Profile trình duyệt độc lập (Portable):**
  * `gphotos_eagle_ai/browser_profile/` *(Chứa toàn bộ cookie, phiên đăng nhập Google Photos để không bao giờ bị hỏi lại)*

---

## 2. Mục Tiêu & Bài Toán Nghiệp Vụ Của Dự Án

* **Bài toán:** Đội ngũ Marketing có hàng ngàn ảnh và video trên Google Photos. Cần đưa vào phần mềm quản lý tài nguyên **Eagle (eagle.cool)** để Content Creator dễ dàng tìm kiếm, lọc theo chủ đề và lấy ra làm bài viết / dựng video.
* **Các điểm nghẽn kỹ thuật đã được giải quyết:**
  1. **Google Photos chặn API:** Kể từ tháng 3/2025, Google không cấp quyền API quét tự động hàng loạt (`photoslibrary.readonly`). Hệ thống đã giải quyết bằng **cơ chế trích xuất link siêu tốc bằng JavaScript trên Console (Tốn 0 Token AI)**.
  2. **Tiết kiệm Token & Chi phí AI tối đa:**
     - Ảnh thường được tự động nắn kích thước về 512px (chi phí chỉ ~0.0001$/ảnh).
     - Video được cắt ghép thành **Lưới khung hình đại diện (Contact Sheet 3x3 = 9 ô có timestamp)** bằng OpenCV/FFmpeg. AI chỉ cần xem 1 tấm ảnh duy nhất để hiểu toàn bộ clip, **tiết kiệm 95% token**.
  3. **Đăng nhập Google Photos 1 lần duy nhất:** Dùng Profile Chrome độc lập lưu trực tiếp trong thư mục backend (`browser_profile/`), mang đi máy nào phiên đăng nhập vẫn giữ nguyên.
  4. **Tích hợp sâu với Eagle:** Gọi thẳng **Eagle Local API (`localhost:41595`)** để tự động tạo cây thư mục Marketing, gắn Tags, chấm điểm 1–5 sao, gợi ý góc làm Content.

---

## 3. Bản Đồ Mã Nguồn & Trách Nhiệm Từng File

```text
gphotos_eagle_ai/
├── 1_Dang_Nhap_Google_Photos.bat       # [Win] 1-Click mở Chrome độc lập để đăng nhập Google Photos
├── 1_Dang_Nhap_Google_Photos.command   # [Mac] 1-Click mở Chrome độc lập (dùng lệnh open -na ép tạo instance mới)
├── 2_Chay_Phan_Loai_Eagle.bat          # [Win] 1-Click bật server & mở Web Dashboard (http://127.0.0.1:8899)
├── 2_Chay_Phan_Loai_Eagle.command      # [Mac] 1-Click bật server & mở Web Dashboard
├── config.json                         # Cấu hình API key, port Eagle, 6 danh mục Marketing chuẩn
├── eagle_client.py                     # Client gọi Eagle Local REST API (localhost:41595)
├── media_processor.py                  # Module tối ưu ảnh (512px) & tạo lưới video Contact Sheet (3x3)
├── ai_classifier.py                    # Module AI Vision (hỗ trợ cả Gemini 2.5 Flash lẫn GPT-4o)
├── gphotos_extractor.py                # Mã JS bóc tách link Google Photos (0 token) & bộ mở browser
├── server.py                           # Mini Web Server (Python standard library, không lo thiếu framework)
├── mcp_bridge.py                       # Cổng Model Context Protocol (MCP) chuẩn cho GPT / Antigravity
├── browser_profile/                    # THƯ MỤC CHỨA DỮ LIỆU ĐĂNG NHẬP GOOGLE PHOTOS (PORTABLE)
├── static/                             # Giao diện Web Dashboard (Dark Mode Apple-style)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── README.md                           # Hướng dẫn sử dụng cho người dùng cuối
└── GPT_HANDOVER.md                     # File bàn giao này
```

---

## 4. Cách GPT / AI Agent Kết Nối & Điều Khiển Dự Án

### Cách 1: Qua chuẩn MCP (Model Context Protocol) - Khuyên Dùng
Nếu bạn (hoặc ChatGPT Desktop / Claude / Antigravity) hỗ trợ MCP, hãy thêm server này vào file cấu hình agent:

```json
{
  "mcpServers": {
    "gphotos-eagle": {
      "command": "python",
      "args": [
        "c:/Users/Admin/Documents/antigravity/amazing-curie/gphotos_eagle_ai/mcp_bridge.py"
      ]
    }
  }
}
```

**Các công cụ MCP sẵn có để GPT gọi:**
* `get_eagle_status()`: Kiểm tra Eagle có đang bật không, đã phân loại được bao nhiêu ảnh/video.
* `classify_media_file(file_path, custom_instruction)`: Soi 1 file ảnh/video, tạo lưới, gán nhãn marketing và bắn vào Eagle.
* `scan_folder_into_eagle(folder_path, custom_instruction)`: Quét cả thư mục ảnh Takeout vào Eagle.
* `open_google_photos_session(album_url)`: Mở cửa sổ Chrome độc lập vào đúng album cần xem.

### Cách 2: Qua Local REST API
Khi server đang chạy tại `http://127.0.0.1:8899`:
* `GET /api/status`: Lấy tiến độ quét, số lượng ảnh đã phân loại theo từng nhóm.
* `POST /api/open-chrome`: `{ "url": "https://photos.google.com" }`
* `POST /api/start-scan`: `{ "items": [...], "custom_instruction": "..." }`
* `POST /api/process-item`: `{ "item": { "url": "...", "path": "..." }, "custom_instruction": "..." }`

---

## 5. Quy Trình Vận Hành Chuẩn (Standard Operating Procedure)

1. **Khởi động:** Bật Eagle trên máy ➔ Chạy file `2_Chay_Phan_Loai_Eagle.bat` (hoặc `.command` trên Mac).
2. **Đăng nhập Google Photos:** Chạy `1_Dang_Nhap_Google_Photos.bat` (hoặc `.command`) ➔ Đăng nhập tài khoản 1 lần.
3. **Bóc tách link:** Mở Album trên Google Photos ➔ Mở Console F12 ➔ Dán mã trích xuất từ nút *"📋 Mã bóc tách link siêu tốc"* ➔ Tải file `gphotos_export.json` (chỉ mất ~20 giây cho 1.000 ảnh, 0 token AI).
4. **Phân loại vào Eagle:** Nạp file `gphotos_export.json` vào Dashboard ➔ Bấm *"Bắt đầu quét & Đẩy vào Eagle"* ➔ AI chạy đa luồng, rót ảnh thẳng vào từng thư mục Eagle theo thời gian thực.

---

## 6. Bộ Khung Phân Loại Marketing Chuẩn (`config.json`)

Mặc định đã thiết lập 6 danh mục tối ưu cho đội Content:
1. `01_Sản phẩm nổi bật (Hero)`: Ảnh cận cảnh nét, ánh sáng đẹp chuẩn quảng cáo.
2. `02_Feedback & Khách hàng`: Khách hàng trải nghiệm sản phẩm, cảm xúc tự nhiên, nụ cười.
3. `03_B-Roll & Cảnh chèn`: Góc máy nghệ thuật, không gian, thao tác phục vụ dựng video.
4. `04_Hậu trường & Đội ngũ`: Quá trình làm việc, nhân sự, kho xưởng.
5. `05_Sự kiện & Hoạt động`: Khai trương, hội thảo, tiệc, team building.
6. `06_Ảnh trùng & Loại bỏ`: Ảnh mờ nét, rung tay, nhắm mắt hoặc ảnh chụp liên thanh thừa.

---

## 7. Ghi Chú Kỹ Thuật Quan Trọng Khi Phát Triển Tiếp

* **Cross-platform macOS lưu ý:** Khi gọi Chrome trên macOS, bắt buộc phải dùng cú pháp `open -na "Google Chrome" --args --user-data-dir="..."` (cờ `-n` ép Mac tạo Process riêng biệt, không bị gộp vào Chrome cá nhân của người dùng).
* **Đổi nhà cung cấp AI:** Trong `config.json`, trường `"ai.provider"` có thể chuyển đổi tự do giữa `"gemini"` và `"openai"`.
* **Kéo thả tức thì:** Thư viện hỗ trợ cả việc kéo thả (Dropzone) ảnh trực tiếp trên web dashboard để phân loại lẻ từng tấm.
