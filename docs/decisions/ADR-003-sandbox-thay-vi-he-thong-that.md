# ADR-003 — Sandbox mô phỏng thay vì thao tác trên hệ thống thật

Ngày: 2026-09-18 · Người quyết: sản phẩm (idea §4, §5) — chốt bởi orchestrator E01 · Trạng thái: **chốt** · Liên quan: nguyên tắc bất biến 1 (plan §1), E02, E05, E08, E09; N06, SEC-05, SEC-06, C02-gap

## Bối cảnh
Dạy kỹ năng số trên tài khoản thật (VNeID, ngân hàng, eTax) rủi ro mất tiền/lộ dữ liệu, không lặp lại được, và không đo được; Cục Thuế đã mở "cổng trải nghiệm" chứng minh nhu cầu sandbox là thật (idea §2). Agent có tool hành động trên hệ thống thật là bề mặt tấn công lớn nhất (OWASP Agentic). Mô-đun "kèm cặp trên app thật" kéo theo ảnh có CCCD/OTP của người dùng vào hệ thống (SEC-05) và đòi OCR + tập ảnh thật (N06).

## Lựa chọn
- Mọi kỹ năng được dạy trong **sandbox**: máy trạng thái JSON (`sandbox/scenarios/*.json`, schema brief §5), giao diện React dựng theo bố cục app thật nhưng nhãn "Ứng dụng mô phỏng", dữ liệu giả (`fake_data`), không gọi hệ thống thật; agent nhận **trạng thái có cấu trúc**, không cần đọc ảnh trong sandbox; `coach_line`/`hint` sinh sẵn nên bước sandbox không gọi LLM (p95 < 1 s — F05).
- **Không tool nào** của agent có side effect ngoài `none | sandbox | log` (`config/tools.yaml`, `tests/invariants`); không tool gửi tiền, gửi tin, gọi API ngoài; guardrail `refuses_real_action` từ chối "làm giúp tôi trên app thật".
- Kèm cặp tại chỗ (E08) ở bản nộp và chung kết **chỉ đọc ảnh màn hình sandbox** (VLM trả `screen_id` thuộc catalog); "kèm cặp trên app thật" là **hướng phát triển** (mục 12 hồ sơ) với điều kiện mở lại: OCR mã nguồn mở Apache/MIT, tập ảnh có đồng thuận riêng, bộ eval `pii-redaction` recall ≥ 0,99, ADR mới.
- Vắc-xin lừa đảo: mô phỏng ở mức mẫu hành vi trong sandbox có nhãn "Đây là mô phỏng"; không lời thoại hoàn chỉnh; không kênh thật (SMS/Zalo thật) — D27.
- Lớp không có mạng: PWA offline chạy sandbox (E12) thay APK.

## Hệ quả
- Giá trị: an toàn tuyệt đối cho người học, đo được từng bước, tái lập được; câu trả lời "khác gì ChatGPT" rõ ràng (idea §13).
- Giới hạn phải nói thật trong hồ sơ: kỹ năng học trong mô phỏng có thể lệch giao diện app thật theo thời gian → kịch bản là JSON cập nhật không cần lập trình; "kèm cặp trên app thật" chưa có ở bản nộp.
- Test bảo vệ: `tests/invariants` (a) side effect, `sandbox/tests` (nhãn "mô phỏng", `never_ask`), `make redteam` ca "làm giúp tôi trên app thật".

## Trạng thái
2026-09-18 chốt. Xem lại chỉ khi BTC/đối tác yêu cầu tích hợp API thật (ngoài phạm vi plan §2) — khi đó cần ADR mới và đánh giá rủi ro theo NĐ 142/2026.
