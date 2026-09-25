# ADR-005 — Chính sách dữ liệu: không PII, hash thay nguyên văn, TTL ảnh 60 s, thời hạn lưu, nơi lưu, đồng thuận

Ngày: 2026-09-18 · Người quyết: orchestrator E01 theo brief §4, D5, D21, D25, D28 · Trạng thái: **chốt** (bảng retention có thể siết thêm qua ADR mới, không nới) · Liên quan: nguyên tắc bất biến 2, `config/app.yaml`, E02, E08, PILOT, DOSSIER; SEC-01, SEC-04, SEC-05, ETH-12, N09, LIC-10

## Bối cảnh
"Không lưu dữ liệu định danh" trong ba file chỉ được hiểu hẹp (CCCD/STK/OTP/mật khẩu) trong khi schema vẫn cho lưu nội dung tự do (`events.payload_json`, `qa_logs`), ảnh app thật có PII, dữ liệu pilot và prompt log công khai chưa có bước lọc; cam kết "máy chủ trong nước" chưa khớp lựa chọn GPU (ETH-12); thông tin cá nhân thành viên đội có nguy cơ vào repo public (N09). Cơ sở pháp lý: Luật 134/2025/QH15, NĐ 142/2026/NĐ-CP (đã xác minh); Luật 91/2025/QH15, NĐ 356/2025/NĐ-CP **chưa xác minh** (`docs/legal/refs.yaml`).

## Lựa chọn
- **Không có cột PII**: `users` chỉ `display_name` (biệt danh/mã do TNV cấp — không họ tên), `role`, `class_id`, `accent_pref`, `consent_at`; không CCCD/điện thoại/email/địa chỉ; họ tên chỉ trên phiếu giấy do trưởng nhóm giữ, hủy sau 90 ngày. `qa_logs` chỉ `question_hash`/`answer_hash` (HMAC với salt máy chủ). `events.payload_json` allowlist theo `type`: input ⇒ `{field_id, valid, len}`; tap ⇒ `{target}`; ask ⇒ `{intent_class, hmac}`; `screen_jobs.boxes_json` ⇒ `[{cls,x,y,w,h}]` cấm text; `audit.target` ⇒ uuid. Regex PII (`config/guardrails.yaml`) chạy ở tầng ghi và trong `ctcv_core.logging`.
- **Ảnh màn hình**: chỉ trong MinIO bucket `screens`, TTL `screen_ttl_seconds = 60`, không backup; PII làm mờ theo bbox **trước khi lưu** (model tự host nên ảnh vào model rồi che trước khi ghi — F08); VLM/planner không bao giờ đọc số từ màn hình; v1.0 chỉ ảnh sandbox (ADR-003).
- **Giọng nói**: ASR xử lý trong bộ nhớ, không ghi file; audio chỉ được lưu khi có ô đồng ý riêng trên phiếu (cho tập đánh giá CC-BY hoặc ASR LoRA tương lai).
- **Bảng retention** (D28):

| Dữ liệu | Thời hạn | Ghi chú |
| --- | --- | --- |
| `events`, `sessions`, `qa_logs`, `drills` | 90 ngày | xóa theo lịch; xóa sớm theo yêu cầu qua TNV (theo mã số) |
| Log ứng dụng JSON | 30 ngày (`log_retention_days`) | không PII, có `request_id` |
| Ảnh màn hình | 60 s | không backup |
| Backup PostgreSQL/Qdrant | 14 bản × 6 giờ | object storage khác máy, trong nước; không chứa ảnh |
| Dữ liệu pilot thô (log, phiếu SUS nhập) | 90 ngày | máy chủ trong nước; **không bao giờ** lên Drive/repo (D21) |
| Prompt log Claude Code | vĩnh viễn (minh chứng BTC) | qua redaction gate trước khi công khai |

- **Nơi lưu**: PostgreSQL/Qdrant/MinIO trên máy chủ đặt tại Việt Nam (VPS/GPU nhà cung cấp trong nước nếu có); Cloudflare DNS-only; nếu buộc dùng GPU nước ngoài cho phục vụ, hồ sơ ghi trung thực và dữ liệu pilot vẫn ở máy trong nước (ETH-12).
- **Đồng thuận**: phiếu giấy chữ to (mã số thay tên), câu "giọng nói chuyển thành chữ ngay và không lưu", ô riêng cho ghi âm và ảnh câu chuyện; quyền xóa qua TNV; trẻ em không phải đối tượng.
- **Prompt log công khai** (SEC-01/D21): `make promptlog-export` chạy gitleaks + regex PII; phát hiện → thay `[REDACTED-SECRET sha256:<8>]`, ghi trong INDEX/README (chính sách công bố, không phải sửa log).
- **Thông tin đội** (N09): `docs/dossier/private/team.yaml` (gitignore) + gitleaks rule SĐT/email VN cho `docs/**`; Drive chỉ chứa PDF đã điền.
- **Kho hướng dẫn** (LIC-10): `data/raw`, `data/clean` gitignore; repo chỉ có `data/sources.yaml` + manifest hash; UI hiển thị trích ≤ 2 câu + link.

## Hệ quả
- Không có "quyền truy cập dữ liệu người dùng" nào để bị lạm dụng; tuân thủ tối thiểu hóa dữ liệu; mục 11 hồ sơ có bảng retention và cơ sở pháp lý đã xác minh.
- Mất một số phân tích (không biết ai học lâu dài ngoài mã số); "quay lại ngày 5" đo bằng mã lớp + thẻ QR, không Zalo.
- Test: `tests/invariants` (b), `services/api/tests` allowlist, `services/vision/tests` TTL 60 s và redact-trước-lưu, `scripts/tests` cho promptlog_export.

## Trạng thái
2026-09-18 chốt. Xem lại khi: xác minh xong Luật 91/2025 và NĐ 356/2025 (có thể siết), đối tác pilot yêu cầu khác, hoặc mở lại "kèm cặp trên app thật".
