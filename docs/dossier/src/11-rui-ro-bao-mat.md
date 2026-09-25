# 11. Phân tích rủi ro, yêu cầu bảo mật, đạo đức trí tuệ nhân tạo và an toàn dữ liệu

> Nội dung trình bày: Nêu các rủi ro có thể phát sinh khi sử dụng sản phẩm; biện pháp bảo mật, bảo vệ dữ liệu; phương án kiểm soát đầu ra; yêu cầu về đạo đức trí tuệ nhân tạo, quyền riêng tư và an toàn thông tin.

CTCV thiết kế theo nguyên tắc "không có gì để mất", với ba nguyên tắc bất biến có test tự động: (1) không tool nào tác động lên hệ thống thật; (2) không lưu CCCD, số tài khoản, OTP, mật khẩu — ảnh màn hình xóa sau 60 giây; (3) mọi dữ kiện đọc cho người dân phải có nguồn.

## 11.1. Rủi ro và biện pháp

| Rủi ro | Mức | Biện pháp | Kiểm tra |
| --- | --- | --- | --- |
| Prompt injection qua văn bản dán, tin nhắn mẫu, nội dung web, ảnh | Cao | LLM cách ly trả schema kín (enum ý định, mã dấu hiệu, số tiền, danh mục cơ quan); chunk RAG vào planner sau kiểm chứng và lọc câu mệnh lệnh; VLM chỉ trả `screen_id`/`element_id` thuộc danh mục | Red-team 50 → 200 = 0; test bất biến "không chuỗi tự do vào planner" |
| Bị dụ hỏi OTP/mật khẩu hoặc "làm giúp trên app thật" | Cao | Quy tắc cứng từ chối; whitelist 8 tool, side effect chỉ `none/sandbox/log`; không tool gửi tiền, gửi tin, gọi API ngoài | Red-team; test bất biến tool registry |
| Ảnh màn hình chứa dữ liệu nhạy cảm | Trung bình | Bản nộp chỉ nhận ảnh sandbox; ảnh app thật là hướng phát triển (OCR mở, recall che PII ≥ 0,99); ảnh sống 60 giây; prompt VLM cấm chép chuỗi số ≥ 4 ký tự | Test TTL; ca red-team "ảnh chứa OTP/số dư" |
| Kịch bản lừa đảo bị dùng ngược | Trung bình | Chỉ mô tả dấu hiệu; 1 lượt thoại ≤ 40 từ có nhãn "[Mô phỏng]"; cấm URL, số điện thoại, số tài khoản, tên thật; không endpoint liệt kê; rate limit; `qr_token` có hạn, thu hồi được | Validator drills; ca red-team "viết kịch bản lừa hoàn chỉnh" |
| Hallucination, nội dung lỗi thời | Trung bình | Trích dẫn bắt buộc kèm ngày hiệu lực; dưới ngưỡng tin cậy → tình nguyện viên; kho đóng băng theo phiên bản | Citation-support ≥ 95%, hallucination ≤ 3% |
| Máy chủ GPU sập khi chấm | Thấp | Tầng luôn bật CPU + failover DNS ≤ 5 phút; trang status công khai | Uptime Kuma |
| Rò rỉ bí mật/PII qua Prompt Log công khai | Trung bình | `make promptlog-export` chạy gitleaks + regex PII; phát hiện → thay bằng `[REDACTED-SECRET sha256:…]`, ghi trong INDEX (chính sách công bố, không sửa log); dữ liệu pilot thô không lên Drive | Cổng export |

## 11.2. Yêu cầu bảo mật và an toàn dữ liệu

HTTPS (Caddy), JWT ngắn hạn, phân quyền 3 vai, rate limit; `user_id` lấy từ JWT, không phải tham số tool; `events.payload_json` có allowlist trường theo loại sự kiện, không lưu nguyên văn; `qa_logs` chỉ giữ hash; `display_name` là biệt danh; log không PII. Thời hạn lưu (ADR-005): dữ liệu học 90 ngày, log 30 ngày, backup 14 bản; quyền xóa qua tình nguyện viên; gitleaks, pip-audit, pnpm audit và kiểm tra giấy phép chạy mỗi PR.

## 11.3. Tuân thủ pháp luật

Số hiệu và ngày hiệu lực đã đối chiếu trên Cổng thông tin điện tử Chính phủ (`docs/legal/refs.yaml`, 19/9/2026).

| Yêu cầu | Văn bản | CTCV đáp ứng bằng |
| --- | --- | --- |
| Quản lý AI theo mức rủi ro, minh bạch, giải trình | Luật Trí tuệ nhân tạo 134/2025/QH15 (hiệu lực 1/3/2026); Nghị định 142/2026/NĐ-CP (hiệu lực 1/5/2026) | Tự đánh giá thuộc nhóm rủi ro thấp: hỗ trợ học tập, không ra quyết định về quyền lợi, không tác động lên hệ thống thật; mô tả mục đích, nguyên lý, nguồn dữ liệu và biện pháp kiểm soát trong hồ sơ; nhãn "nội dung do AI tạo" trên phản hồi và giọng tổng hợp |
| Đạo đức AI | Thông tư 05/2026/TT-BKHCN ban hành Khung đạo đức trí tuệ nhân tạo quốc gia (10/3/2026) | Áp dụng tự nguyện như chuẩn tham chiếu: an toàn ngay từ thiết kế, con người giám sát (nút gọi tình nguyện viên), minh bạch nguồn, công bằng vùng miền |
| Bảo vệ dữ liệu cá nhân | Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP (cùng hiệu lực 1/1/2026) | Thu tối thiểu (biệt danh, mã lớp), đồng thuận bằng phiếu chữ to, quyền xóa qua tình nguyện viên, lưu trong nước, không ghi âm, không thu dữ liệu nhạy cảm |

## 11.4. Đạo đức AI và bao trùm

- Người cao tuổi dễ tổn thương: không áp lực thời gian, không xếp hạng công khai, lỗi nói bằng giọng khích lệ; luôn có nút "Gọi tình nguyện viên" — sản phẩm tăng năng suất phong trào, không thay người.
- Công bằng vùng miền: WER báo cáo riêng từng giọng; giọng kém hơn 6 điểm được ưu tiên cải thiện.
- Minh bạch: nút "Nguồn" ở mỗi câu trả lời; nội dung mô phỏng luôn có nhãn; mã nguồn mở; không thu dữ liệu để bán; không sửa Prompt Log hay lịch sử commit.
