# Google Photos → Agent Vision → Eagle

## Mở ứng dụng

Dashboard: http://127.0.0.1:8899/ (8898 cũng mở cùng ứng dụng).
MCP: http://127.0.0.1:8898/mcp. Codex và Antigravity đã có địa chỉ này.
Một process chạy cả hai cổng, dùng cùng SQLite tại `v2/data/catalog.sqlite` để giữ dữ liệu cũ.

## Cấu Hình Kết Nối Dành Cho AI Agent (Antigravity / Claude / Cursor)

Hệ thống đã tích hợp sẵn tệp cấu hình và tài liệu chỉ dẫn tự động cho AI Agent:
* **`mcp_config.json` / `.mcp.json`**: Cấu hình chuẩn kết nối thẳng vào `http://127.0.0.1:8898/mcp`.
* **`GEMINI.md` / `AGENTS.md`**: File chỉ dẫn tự động cho Antigravity (Anti) khi mở thư mục dự án này.
* **`ANTIGRAVITY_CONNECT_TOOL.md`**: Cẩm nang kết nối và quy trình vận hành 45 MCP Tools.
* **`SKILL.md`**: Cẩm nang kỹ năng `universal-media-classifier` đa ngành (Spa, F&B, Gym, Nha khoa).

## Luồng làm việc

1. Chọn kho Photos hiện có hoặc thêm profile riêng, mở Photos để đăng nhập. Có thể dán link album. Đăng nhập là trên trang Google; phiên có thể hết hạn.
2. Giữ cách bóc link từ bản cũ: sao chép mã, dán Console trong Photos, tải JSON và nạp Dashboard. Hoặc dùng thư mục/Takeout, link CDN Google, kéo thả file (50 MiB).
3. Nhập nghiệp vụ và budget, tạo tác vụ. Việc nạp ảnh/index chạy nền. Tác vụ chờ agent, không gọi API AI.
4. Agent gọi `list_jobs`, lấy batch, xem riêng ảnh cần giữ, mô tả theo `content_policy.json`, lưu quyết định. Dashboard hiển thị cùng dữ liệu.
5. Chọn ảnh keep trên trang kết quả, đọc thư viện Eagle hiện tại rồi nhập. Không xóa nguồn.

## Những phần được giữ và gộp

- Giữ bố cục/CSS Dashboard cũ, mở Google Photos và `browser_profile/`, crawler JSON, local/video, kéo thả và Eagle.
- `core.py` dùng chung cho Dashboard/MCP/CLI. `eagle_client.py` là nơi gọi Eagle; không có bản client riêng trong core.
- Danh mục mới dùng tên tiếng Việt tương ứng bản cũ; điểm sao được ánh xạ từ quality khi không có rating. Job đã tạo giữ snapshot policy cũ.
- Root `server.py` và v2 entrypoint chỉ là wrapper tương thích. Không còn hai bộ xử lý độc lập.
- Bỏ module gọi API Gemini/OpenAI, MCP legacy và test cho đường API cũ khỏi runtime. Bản sao trước gộp lưu trong `backups/` (không chứa profile/cache).

## Cấu trúc

`server.py` → `http_service.py` → `dashboard.py` + `mcp_bridge.py` → `core.py` → `store.py`, `media.py`, `eagle_client.py`.
`gphotos_extractor.py` mở profile và cung cấp crawler; `static/` là Dashboard duy nhất.
`content_policy.json` quản lý quy tắc/tag/danh mục có version.
`v2/data/` giữ catalog/cache cũ; profile thêm mới nằm dưới đó. `browser_profile/` giữ nguyên.

## Giới hạn thực tế

- Chưa tự duyệt/chọn album bằng DOM. Crawler vẫn là bước Console của bản trước, chưa được xác minh bao phủ toàn bộ kho.
- Link CDN/JSON có thể là thumbnail; byte tải về chưa chắc là bản gốc. Dùng Takeout/local để bảo đảm file gốc. Video qua link chưa hỗ trợ.
- Nhóm chính xác bằng SHA; dHash mới dùng sắp ứng viên, chưa là near-duplicate clustering. Chưa có cache quyết định qua job hoặc semantic search.
- HTTP chỉ loopback, kiểm tra Host/Origin. Dashboard mutation cần token local. MCP tin cậy các process trên máy; không công khai cổng ra Internet.
- Import uncertain không tự retry. Chưa có công cụ đối soát tự động hoặc backup profile hoàn chỉnh.
- Tác vụ nạp nguồn đang chạy có thể bị ngắt khi thoát app; index từng file đã ghi được giữ, có thể nạp lại. Không quảng cáo resume download hoàn chỉnh.

## Vận hành

Python 3.11+, `python -m pip install -r requirements-vision.txt`.
`python server.py`; nếu đã chạy thì chỉ mở web, không bật process thứ hai.
Shortcut Startup hiện có vẫn hoạt động qua wrapper `v2/http_service.py`.
Test: `python -m unittest test_vision test_merge -v` (không gọi model/Eagle thật).
CLI: `python cli.py list_sources --data v2/data`.

Không cần API key GPT/Gemini. Model Vision nằm trong agent host.
