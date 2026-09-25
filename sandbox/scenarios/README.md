# Kịch bản sandbox (`sandbox/scenarios/*.json`)

Mỗi file là **một máy trạng thái JSON** (màn hình → phần tử → hành động hợp lệ → lỗi thường gặp) mà giao diện web dựng lại dưới nhãn "Ứng dụng mô phỏng". Không file nào gọi tới hệ thống thật; mọi số liệu trong `fake_data` là giả.

- Schema: `config/schemas/scenario.schema.json` (sinh từ `ctcv_sandbox.schema.Scenario` bằng `make schemas`).
- Kiểm tra: `uv run python -m ctcv_sandbox.validate` (mặc định quét cả thư mục này; mã thoát 1 khi có lỗi).
- Tên file **phải trùng** trường `id`.

## 12 kịch bản (id cố định — brief E01 §5)

| # | `id` | Nhóm kỹ năng (`skill_group`) | Epic giao |
| --- | --- | --- | --- |
| 1 | `chuyen-khoan-qr` | `thanh-toan-thue-so` | **E01** (mẫu, mức 1 — đã có) / E02 hoàn thiện |
| 2 | `dang-nhap-vneid` | `dinh-danh-vneid` | E02 |
| 3 | `xac-nhan-cu-tru` | `dich-vu-cong` | E02 |
| 4 | `ke-khai-doanh-thu` | `thanh-toan-thue-so` | E02 |
| 5 | `xuat-trinh-giay-to` | `dinh-danh-vneid` | E10 |
| 6 | `khai-sinh-truc-tuyen` | `dich-vu-cong` | E10 |
| 7 | `kiem-tra-bien-dong-so-du` | `thanh-toan-thue-so` | E10 |
| 8 | `cai-app-kho-chinh-thuc` | `thiet-bi-co-ban` | E10 |
| 9 | `doi-mat-khau` | `an-toan-so` | E10 |
| 10 | `bat-xac-thuc-2-lop` | `an-toan-so` | E10 |
| 11 | `thanh-toan-qr-cua-hang` | `thanh-toan-thue-so` | E10 |
| 12 | `goi-video-zalo` | `thiet-bi-co-ban` | E10 |

Mỗi kịch bản có thể có tới 3 mức (`level` 1..3, plan §7 bước 4: 12 × 3 file); E02 viết tay 4 kịch bản mức 1 làm few-shot cho bước sinh dữ liệu ở E06.

## Quy tắc bắt buộc (validator từ chối nếu vi phạm)

1. `app_label` phải chứa "mô phỏng"; `never_ask` phải có `otp` và `mat_khau`.
2. `start_screen` tồn tại; mọi màn hình đến được từ `start_screen`; màn hình không kết thúc phải có `valid_actions` và có đường tới màn hình kết thúc.
3. Hành động/lỗi thường gặp chỉ trỏ tới phần tử có trên màn hình và màn hình có thật; `tap` không trỏ vào ô nhập, `input` chỉ trỏ vào ô nhập.
4. `success.screen` là màn hình kết thúc (`terminal: true`); khóa trong `success.conditions` là id của một ô nhập.
5. `coach_line` và `hint` ≤ `max_sentences` câu (config/guardrails.yaml) và không chứa `banned_terms` (thuật ngữ).
6. Ô nhập có id/nhãn trùng `never_ask` (OTP, mật khẩu, số thẻ…) phải đánh dấu `sensitive: true`; engine không bao giờ lưu giá trị của ô nhạy cảm.

## Thêm kịch bản mới (không cần lập trình)

1. Chép `chuyen-khoan-qr.json`, đổi `id` (trùng tên file), `goal`, `intent_confirmation`.
2. Viết từng màn hình: phần tử (nút/ô nhập/chữ/băng rôn, màu gọi tên được), hành động đúng, 1–2 lỗi thường gặp kèm câu gợi ý ngắn.
3. Chạy `uv run python -m ctcv_sandbox.validate sandbox/scenarios/<id>.json` đến khi in `OK`.
