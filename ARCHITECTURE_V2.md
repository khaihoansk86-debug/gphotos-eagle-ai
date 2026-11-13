# Google Photos → Agent Vision → Eagle: kiến trúc V2

Ngày: 2026-11-12. Trạng thái: thiết kế đích để triển khai, không phải mô tả các tính năng đã chạy.

## 1. Quyết định nền tảng

- Antigravity/Codex hoặc một agent hỗ trợ công cụ và ảnh là bộ phận suy luận Vision. Người dùng sử dụng tài khoản/model trong agent; ứng dụng này không giữ khóa hoặc gọi API GPT/Gemini.
- MCP là giao diện ưu tiên; CLI dùng cùng lõi khi host không hỗ trợ MCP. Không tự động thao tác giao diện chat ChatGPT/Gemini làm luồng chính.
- Host phải thực sự chuyển image content từ MCP vào model Vision. Đăng nhập tài khoản hoặc hỗ trợ MCP text chưa đủ. Bắt buộc kiểm tra khả năng này trước khi chạy kho thật.
- Việc đọc Photos, lập chỉ mục, tạo thumbnail, tìm trùng, lưu trạng thái và nhập Eagle do code trên máy thực hiện. Agent không dùng screenshot để cuộn hàng nghìn ảnh.
- Không thể bảo đảm subscription ChatGPT/Gemini dùng được trong mọi host. Khả năng model, hình ảnh, xác thực và hạn mức phụ thuộc host đã chọn.
- Không cam kết một tỷ lệ tiết kiệm token cố định. Đo số ảnh/lượt/pixel/thời gian; chỉ ghi token khi host cung cấp số liệu thật.

## 2. Luồng tổng thể

```text
Người dùng: chọn kho + album + yêu cầu + bộ danh mục + giới hạn lượt Vision
                                      |
Dashboard / agent ---------> Core + SQLite <---------- MCP / CLI
                               |
          +--------------------+-----------------------+
          |                    |                       |
  Photos collector      Xử lý cục bộ              Eagle Local API
  profile từng kho      hash/nhóm/thumbnail       tải gốc → nhập → đối soát
          |                    |
          +----------> hàng đợi nhóm ảnh
                               |
                   MCP trả bảng ảnh có mã
                               |
                       Agent Vision
                               |
                 cần chi tiết? mở ảnh/crop
                               |
                   lưu quyết định có cấu trúc
                               |
                   duyệt/commit theo chế độ
```

Không có dịch vụ phân loại AI độc lập trong backend. Model được host gọi khi agent xử lý kết quả công cụ. Dashboard không tự kích hoạt model trong host nếu host chưa cung cấp cơ chế dispatch; mặc định người dùng tạo job trên Dashboard và yêu cầu agent chạy `job_id` đó.

## 3. Cấu trúc mã đích

```text
gphotos_eagle_ai/
├── README.md                    # Cài đặt, vận hành, giới hạn đã xác minh
├── GPT_HANDOVER.md              # Trạng thái triển khai và việc còn lại
├── ARCHITECTURE_V2.md           # Thiết kế này
├── config.json                 # Cấu hình không chứa khóa AI/cookie
├── core.py                     # Use cases, kiểm tra dữ liệu, state machine
├── store.py                    # SQLite, migration, giao dịch, cursor/lease
├── photos.py                   # Profile, album, collector, tải gốc, checkpoint
├── media.py                    # Thumbnail, hash, chất lượng, bảng ảnh/crop/video
├── eagle_client.py             # Tái sử dụng client Eagle; đối soát nhập
├── mcp_bridge.py               # Tool/resource schema; image content và lỗi MCP
├── cli.py                      # Gọi core, xuất JSON và đường dẫn ảnh
├── server.py                   # Dashboard local; chỉ chuyển yêu cầu vào core
├── static/                     # Kho, job, hàng đợi, duyệt và trạng thái Eagle
├── tests/                      # Kiểm tra các ranh giới và luồng hoàn chỉnh
└── data/                       # Dữ liệu runtime, không đưa vào Git
    ├── catalog.sqlite
    ├── profiles/<source_id>/    # Một profile trình duyệt cho mỗi kho Photos
    ├── thumbs/<content_key>/
    ├── sheets/<batch_id>/
    ├── originals/<asset_id>/    # Tải khi thật sự cần; cache có quota
    └── backups/                # Manifest, DB, cấu hình; profile tùy chọn
```

Không thêm service, queue server hoặc vector database riêng. SQLite và thư viện ảnh hiện có là nền ban đầu. Chỉ thêm thư viện browser automation sau khi kiểm chứng collector trên Photos hiện tại; ưu tiên API điều khiển browser hơn script shell và screenshot. MCP nên dùng SDK chính thức với version khóa, thay cho JSON-RPC viết tay. Embedding là bước tùy chọn có benchmark, không phải điều kiện để bản đầu chạy.

## 4. Hồ sơ nguồn và thu thập Google Photos

Mỗi source có ID, tên hiển thị, đường dẫn profile và trạng thái đăng nhập. Profile chỉ phục vụ Photos; không cần chứa phiên GPT/Gemini. Collector mở profile tương ứng, người dùng đăng nhập khi cần. Không trả cookie, token, đường dẫn phiên hoặc URL nhạy cảm vào chat.

Collector chạy nền theo tác vụ, đọc DOM/metadata đang có và cuộn bằng code. Selector phải được kiểm chứng; tài liệu này không giả định Google cung cấp API quét toàn bộ kho hoặc ổn định DOM. Không phá CAPTCHA hoặc cơ chế xác thực. Khi cần người dùng, chuyển `needs_login` và giữ tiến độ.

- Không coi chiều cao trang không đổi là đã hết album: Photos có danh sách ảo hóa. Dừng dựa trên tín hiệu kết thúc được kiểm chứng và số vòng không có ID mới; nếu chưa chắc thì báo `partial`, không báo đủ kho.
- Lưu source ID, album ID, provider item ID và thời điểm thấy item. URL CDN chỉ là địa chỉ tải có thể hết hạn, không phải ID ổn định. Nếu chưa lấy được ID ổn định, đánh dấu danh tính tạm và chưa tự quyết định trùng.
- Một asset có thể thuộc nhiều album: bảng liên kết riêng, không nhân bản ảnh.
- Thumbnail phục vụ lọc; URL thumbnail không được coi là video/ảnh gốc. Khi nhập Eagle, dùng đường lấy bản gốc đã xác minh. Nếu không hỗ trợ, đánh dấu blocked cho item và cho phép nguồn Takeout/local.
- Ghi checkpoint sau từng trang/nhóm; lần chạy tiếp đối chiếu ID để tránh thêm lại. Không bỏ mất mục chỉ vì timestamp checkpoint.
- Một collector giữ độc quyền một profile, tránh hai process làm hỏng profile. Giới hạn tốc độ và backoff khi lỗi.

## 5. Lọc trùng và ảnh cùng góc: không đánh đồng

### Tầng A — trùng byte

SHA-256 của file gốc xác nhận trùng byte. Hash thumbnail giống nhau chỉ xác nhận thumbnail giống nhau; có thể bỏ một lượt xem sơ bộ nhưng không đủ để xóa hoặc kết luận hai bản gốc giống nhau. Giữ liên kết đến mọi bản nguồn.

### Tầng B — gần trùng / cùng cảnh

Dùng perceptual hash và metadata để đề xuất nhóm. Chỉ so trong các bucket phù hợp hoặc cấu trúc tìm lân cận; không so toàn bộ N² ở kho hàng chục nghìn ảnh. Ảnh thiếu ngày vẫn có bucket riêng, không bị loại khỏi xử lý. Không để chuỗi tương đồng A≈B≈C tự khẳng định A≈C; kiểm tra so với ảnh đại diện hoặc tách nhóm.

Độ mờ/phơi sáng/kích thước là tín hiệu xếp ưu tiên, không tự loại ảnh nghệ thuật, chữ hoặc nền đặc biệt. Lưu thuật toán, version và threshold để có thể điều chỉnh.

### Tầng C — giá trị nghiệp vụ bằng Vision

Agent so sánh thành viên nhóm theo yêu cầu người dùng. Cùng góc có thể khác biểu cảm, sản phẩm, động tác hoặc chi tiết cần giữ. Được chọn nhiều ảnh; không ép mỗi nhóm chỉ giữ một ảnh.

Kết quả item: `keep`, `review`, `skip_for_this_job`, `needs_detail`. Không có thao tác xóa bản nguồn trong luồng phân loại. `duplicate_of` phải chỉ tới một asset tồn tại và có lý do; quyết định theo nghiệp vụ chỉ áp dụng trong job đó.

## 6. Vision tiết kiệm ngữ cảnh

1. Bắt đầu bảng 6–12 ảnh, mã ngắn gắn trực tiếp trong ô, kèm batch ID. Đây là mặc định thử nghiệm, không phải kích thước tối ưu đã đo.
2. Bảng có tổng kích thước giới hạn, giữ tỉ lệ ảnh và đủ khoảng cho nhãn. Không ép nhiều ảnh đến mức mặt/chữ không đọc được.
3. Agent yêu cầu ảnh đơn hoặc crop theo asset ID khi chưa đủ bằng chứng. Crop dùng tọa độ chuẩn hóa được kiểm tra; giữ khả năng xem toàn cảnh để tránh đánh giá sai.
4. Chi tiết mặc định kích thước vừa phải; tăng độ phân giải theo nhu cầu và ngân sách. Không gửi lại bản gốc lớn chỉ để xem tổng quan.
5. Video dùng contact sheet có timestamp; cần xem kỹ thì trích frame/đoạn đã yêu cầu. Không tuyên bố hiểu hành động/chuyển động chỉ từ chín frame.
6. Lưu mô tả khách quan tách khỏi quyết định nghiệp vụ. Đổi yêu cầu có thể dùng lại mô tả để tìm ứng viên nhưng cần xem ảnh khi thông tin thiếu.
7. Cache khóa theo nội dung/version, phiên bản tiền xử lý, schema/prompt nghiệp vụ và model provenance khi biết. Không dùng cache quyết định cũ cho yêu cầu mới một cách mù quáng.
8. Tool trạng thái chỉ trả số đếm, cursor và lỗi ngắn. Không trả base64 trong JSON text, không đổ toàn bộ log/danh sách kho vào chat. MCP dùng image content; CLI trả file ảnh để host có công cụ đọc ảnh mở nó.
9. Một lượt lấy batch chỉ trả đúng batch đó. Mỗi job có giới hạn số lượt bảng, lượt chi tiết, tổng pixel gửi và thời gian. Hết giới hạn → `paused_budget`, không kết luận các ảnh còn lại là không phù hợp.
10. Có thể mở chat agent mới để tiếp tục bằng job ID; trạng thái nằm trong DB. Không cần giữ một chat hàng nghìn lượt.

Embedding cục bộ đa ngôn ngữ là tùy chọn để truy vấn mô tả. Dùng để xếp hạng, không mặc định loại phần còn lại. Nếu chỉ kiểm tra top-K thì UI phải nói rõ độ bao phủ; lấy mẫu phần bị bỏ qua để đánh giá tỷ lệ bỏ sót.

## 7. Giao diện MCP tối thiểu

| Tool | Input chính | Output giới hạn |
|---|---|---|
| `list_sources` | cursor, limit ≤ 50 | ID, tên, login status |
| `list_albums` | source_id, cursor, limit | Album ID, tên, trạng thái index |
| `start_index` | source_id, album_ids | operation_id; trả ngay |
| `create_job` | nguồn, nghiệp vụ, taxonomy, budget, commit_mode | job_id, cấu hình hiệu lực |
| `get_job_status` | job_id | tiến độ, coverage, lỗi, next_action |
| `next_vision_batch` | job_id, worker_id | batch_id, lease, mã ảnh + image content |
| `get_asset_view` | job_id, batch_id, asset_id, detail/crop/frame | một image content + metadata ngắn |
| `submit_decisions` | job_id, batch_id, lease, decisions | accepted/rejected counts, lỗi schema |
| `commit_to_eagle` | job_id, decision_ids, idempotency_key | operation_id; chỉ nhập quyết định hợp lệ |
| `control_job` | job_id, pause/resume/cancel | trạng thái bền vững |

Tool catalog giữ gọn. Chức năng đăng nhập, backup, cấu hình và duyệt chủ yếu ở Dashboard/CLI; chỉ thêm tool khi agent thật sự cần điều khiển.

`next_vision_batch` cấp lease có thời hạn. Lặp lại request có request ID phải trả cùng batch thay vì cấp tiếp. Lease hết hạn cho phép nhận lại. `submit_decisions` xử lý atomically, idempotent, kiểm tra mọi asset thuộc batch/job/source; không cho ID từ kho khác lọt vào. `needs_detail` không kết thúc item. Item không có quyết định vẫn pending, không ngầm bị loại.

Lỗi công cụ dùng `isError` và mã lỗi có thể xử lý; exception không thành thông báo thành công. Notification không có response. Initialize, image content, cancel và giao thức SDK phải được kiểm tra với host thật.

Ví dụ kết quả nghiệp vụ:

```json
{
  "job_id": "job_123",
  "batch_id": "batch_17",
  "lease": "opaque-token",
  "decisions": [
    {
      "asset_id": "asset_003",
      "action": "keep",
      "category_id": "product_hero",
      "tags": ["tập tạ", "góc ngang"],
      "rating": 4,
      "reason": "Chủ thể rõ, động tác đủ khung, phù hợp yêu cầu quảng cáo"
    },
    {
      "asset_id": "asset_004",
      "action": "needs_detail",
      "reason": "Cần xem mặt ở ảnh lớn trước khi so với asset_003"
    }
  ]
}
```

## 8. SQLite và trạng thái

Bảng tối thiểu: `sources`, `albums`, `assets`, `album_assets`, `jobs`, `job_assets`, `batches`, `decisions`, `imports`. Chỉ thêm bảng nhóm/quan sát khi implementation cần; không lưu mọi thứ vào một JSON khổng lồ.

- `assets`: ID nội bộ, nguồn/provider ID, loại, metadata, content hash khi có, thumbnail version, cache location. Unique theo source/provider ID khi danh tính ổn định.
- `jobs`: mô tả gốc, taxonomy snapshot, prompt/schema version, phạm vi album snapshot, budgets, trạng thái và coverage.
- `job_assets`: pending/leased/needs_detail/decided; lease và số lần thử.
- `decisions`: append revision có provenance; không ghi đè lịch sử bằng kết quả model mới.
- `imports`: unique theo Eagle library + asset/content identity + import intent; pending/importing/imported/failed/uncertain, Eagle item ID và lỗi.

SQLite WAL, transaction ngắn. MCP và Dashboard dùng cùng DB, không giữ bản sao AppState trong hai process. Không giữ DB lock khi tải ảnh, chờ model hoặc gọi Eagle.

Job: `indexing → ready → reviewing → ready_to_commit → importing → completed`; trạng thái phụ `needs_login`, `paused_budget`, `paused_user`, `failed`, `cancelled`. `completed` không có nghĩa mọi ảnh đều được nhập; luôn kèm số keep/review/skip/failed/pending và coverage.

## 9. Nhập Eagle an toàn và đúng danh mục

- Dùng Eagle Local API, không điều khiển UI Eagle bằng model. API này không phải API model trả phí.
- Taxonomy được xác định từ người dùng và lưu trong job. Model chọn category ID, core ánh xạ ID sang đường dẫn thư mục. Không tạo thư mục trực tiếp từ chuỗi tự do model trả về.
- Cache folder theo library ID + parent ID + tên; không dùng tên đơn lẻ xuyên thư viện.
- Kiểm tra kết nối và thư viện trước commit. Khi library thay đổi, dừng và yêu cầu chọn đích đúng.
- Tải bản gốc được xác minh, kiểm tra định dạng/kích thước; giữ file cho đến khi Eagle xác nhận và có thể đối soát.
- Ghi intent trước request; ghi Eagle ID sau thành công. Nếu timeout sau khi Eagle có thể đã nhập, đánh dấu `uncertain`, đối soát bằng marker/ID được API hỗ trợ; không tự retry mù gây trùng.
- Không hứa exactly-once nếu Eagle API không cung cấp idempotency. Nếu không đối soát chắc chắn được, chờ người dùng kiểm tra.
- Mặc định preview/duyệt; có chế độ auto-commit do người dùng bật cho job. Quyền đã cấp cho job không hỏi lại từng ảnh.

## 10. Dashboard

Ba màn hình chính:

1. **Kho Photos:** tạo/chọn profile, đăng nhập, chọn album, trạng thái thu thập và backup.
2. **Phân loại:** yêu cầu nghiệp vụ, danh mục, budget, tạo job; hiển thị lệnh/job ID cho agent tiếp quản. Không có form API key.
3. **Kết quả:** nhóm ảnh so sánh, mở ảnh đơn, keep/review/skip và lý do; duyệt sửa, nhập Eagle, xem lỗi/retry an toàn.

Luôn hiển thị nguồn ảnh đang dùng là thumbnail hay bản gốc, số đã xem/tổng đã index, số chưa xem, budget tiêu thụ và tình trạng Eagle. Ứng dụng không giả vờ AI đang chạy khi chưa có agent nhận job.

## 11. Backup và giới hạn bảo mật

- Backup SQLite bằng SQLite backup API, không copy mỗi file DB đang bật WAL. Manifest ghi version, source IDs và checksum.
- Profile chỉ backup khi browser đã đóng; loại lock/cache tạm. Backup profile chứa phiên đăng nhập nhạy cảm: không đưa lên Git hoặc gửi qua model; hỗ trợ mã hóa bằng cơ chế đã kiểm chứng, không tự thiết kế mật mã.
- Restore sửa đường dẫn tương đối theo máy, kiểm tra schema và nguồn. Phiên đăng nhập có thể không chuyển được do mã hóa OS hoặc Google yêu cầu xác thực lại; luôn có luồng đăng nhập lại.
- HTTP bind loopback, kiểm tra Origin/Host, không CORS `*` cho cấu hình nhạy cảm. Thao tác sửa cần local session token. Upload giới hạn kích thước, file type và đường dẫn.
- MCP không cung cấp shell tùy ý hoặc đọc đường dẫn tùy ý. Dùng ID và thư mục do ứng dụng quản lý; không cho model viết đường dẫn profile.
- Văn bản trong ảnh/metadata chỉ là dữ liệu, không phải lệnh cho agent. Quyền truy cập và commit được core kiểm tra độc lập với lời model.

## 12. Chuyển đổi từ bản hiện tại

1. **Store + core:** thêm SQLite, job, quyết định và import intent; chuyển xử lý dùng chung ra khỏi `server.py`. Giữ bản cũ chạy được đến khi luồng mới đạt test.
2. **MCP Vision trên thư mục local:** dùng ảnh mẫu/local để kiểm tra host nhận image content, yêu cầu ảnh riêng và submit quyết định. Không gọi AI API. Đây là cổng kiểm chứng trước khi đầu tư collector Photos.
3. **Collector Photos:** profile theo source, chọn album, checkpoint, thu thumbnail và xác minh tải gốc. Nếu DOM không ổn định, hỗ trợ Takeout/local như đường nhập dự phòng có thông báo rõ.
4. **Dedupe + budget + cache:** nhóm ảnh, chính sách xem chi tiết, resume; đo chất lượng trước khi tăng batch.
5. **Dashboard + Eagle:** duyệt, commit, đối soát timeout; backup/restore và hướng dẫn host.
6. **Loại bỏ luồng cũ:** bỏ `ai_classifier.py` và form key sau khi MCP flow được nghiệm thu; thay `gphotos_extractor.py` bằng collector đã kiểm chứng; cập nhật launcher, README và handover theo hành vi thật.

Không xóa profile cũ. Khi chuyển đổi cần đóng browser và tạo source trỏ tới profile cũ trước; không di chuyển thư mục đang sử dụng. Bản thiết kế này không tự kích hoạt migration hoặc chạy phân loại.

## 13. Điều kiện nghiệm thu

- Host thực tế nhận đúng bảng ảnh qua MCP và đọc được mã; lấy ảnh đơn/crop được khi cần.
- Dataset gán nhãn gồm trùng byte, gần trùng, cùng góc khác biểu cảm, ảnh chữ/chi tiết nhỏ, video và ảnh không liên quan. Đo giữ nhầm/bỏ sót theo nghiệp vụ, không chỉ số tool call.
- Kiểm tra restart khi đã lease batch, submit lặp, đổi yêu cầu, hết budget, đổi thư viện Eagle và timeout nhập.
- Kho 20.000 bản ghi kiểm tra pagination/bộ nhớ/thời gian nhóm; không gửi 20.000 item vào context và không chạy so sánh N² toàn kho.
- Collector báo partial khi chưa biết đủ; phiên hết hạn có thể đăng nhập và resume mà không nhập trùng.
- Backup/restore DB giữ checkpoint và decision; profile không phục hồi đăng nhập vẫn có thể xác thực lại.
- So sánh một tập ảnh cố định: xem riêng toàn bộ vs bảng ảnh + detail. Ghi số ảnh đầu vào model, pixel, lượt, thời gian, chi phí/token nếu host báo và độ chính xác. Chỉ công bố mức tiết kiệm sau phép đo.

## 14. Hiện trạng đã xác minh

Bản hiện tại có Dashboard, xử lý ảnh/contact sheet video, client Eagle và MCP JSON-RPC đơn giản. Đã sửa lỗi AI fallback demo, báo thành công Eagle sai, video kéo thả, preview bị cắt và giới hạn 50 item MCP. Bộ kiểm tra hiện tại có 11 test đã đạt trong bản staged.

Chưa có: SQLite/job lease, MCP image workflow, collector Photos có checkpoint ổn định, dedupe, budget, cache quyết định, backup/restore hoàn chỉnh hay kiểm chứng tương thích Antigravity/Codex. Không coi các phần thiết kế trên là đã triển khai.
