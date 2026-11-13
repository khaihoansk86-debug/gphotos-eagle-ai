# Cập nhật 2026-11-12

- Lỗi hoặc thiếu khóa AI dừng xử lý, không dùng kết quả demo để nhập Eagle.
- Kiểm tra danh mục, điểm, tags và các trường văn bản do AI trả về.
- Chỉ báo thành công khi Eagle trả `status: success`; lỗi tạo thư mục cũng dừng nhập.
- Dashboard đếm riêng số thành công/thất bại; preview giữ nguyên dữ liệu ảnh.
- Kéo thả ảnh/video dùng file tạm đúng định dạng; video được tạo contact sheet.
- Kéo thả giới hạn 70 MiB/file; file lớn dùng quét thư mục. HTTP body giới hạn 100 MiB.
- Video từ URL Google Photos chưa được hỗ trợ: tải video gốc về rồi quét thư mục. Link thumbnail không được nhập giả làm video.
- MCP quét toàn bộ thư mục thay vì giới hạn 50 file, báo đúng số lỗi. Lệnh vẫn chạy đồng bộ, thư mục lớn có thể vượt thời gian chờ của MCP host.
- Batch vẫn chạy tuần tự. Chưa có resume/chống nhập trùng. Phiên đăng nhập Chrome có thể hết hạn và không được đảm bảo di chuyển giữa máy.

Kiểm tra: `python -m unittest test_pipeline -v` và `node --check static/app.js`.
Các test giả lập AI/Eagle không gọi API trả phí hay nhập thư viện thật; test video dùng clip tổng hợp cục bộ.
