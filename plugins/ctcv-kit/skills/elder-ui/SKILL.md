---
name: elder-ui
description: Thiết kế giao diện cho người cao tuổi của CTCV — token thiết kế (chữ ≥ 20 pt, vùng bấm ≥ 56 px, tương phản ≥ 7:1, màu có tên), giọng nói là kênh mặc định, một hành động mỗi màn hình, kiểm tra a11y tự động. Use when building, styling or testing any screen in apps/web.
---
# Giao diện cho người 50+ (apps/web)

## Token thiết kế (nguồn sự thật: `config/app.yaml: ui`, hiện thực ở `apps/web/src/theme`, test bằng vitest)
| Token | Giá trị | Ghi chú |
| --- | --- | --- |
| `font.base` | **20 pt** (≈ 26.7 px) tối thiểu; tiêu đề 26–32 pt; phụ đề giọng nói 24 pt | Không có chữ nhỏ hơn 20 pt ở bất kỳ đâu, kể cả nhãn nút, chú thích |
| `tap.min` | **56 × 56 px** tối thiểu; khoảng cách giữa hai vùng bấm ≥ 12 px | Nút chính cao ≥ 64 px, rộng toàn màn hình khi có thể |
| `contrast` | **≥ 7:1** (WCAG AAA) cho chữ thường; ≥ 4.5:1 cho chữ ≥ 24 pt đậm | Kiểm bằng axe/contrast test |
| Màu có tên | `xanh` (chính, xác nhận), `đỏ` (dừng/nguy hiểm), `vàng` (chú ý), `xám` (phụ/tắt), `trắng` (nền), `cam`, `tím` | Trùng danh sách `config/guardrails.yaml: colors`; huấn luyện viên nói "bấm nút **xanh** có chữ **Quét QR**" nên màu phải gọi tên được và nhất quán toàn app |
| Bo góc, bóng | 16 px, bóng nhẹ | Nút trông giống nút; không nút "ma" (ghost) cho hành động chính |
| Chuyển động | Khung động (pulse) quanh bước tiếp theo; không animation trang trí | Tôn trọng `prefers-reduced-motion` |

## Nguyên tắc bố cục
1. **Một hành động chính mỗi màn hình**; tối đa 3 lựa chọn hiển thị đồng thời; không menu ẩn, không vuốt ngang bắt buộc.
2. **Giọng nói là kênh mặc định**: nút micro to ở giữa dưới, sóng âm khi đang nghe, phụ đề chữ to của cả câu người dân nói lẫn câu huấn luyện viên; văn bản luôn song song với âm thanh.
3. Luôn có hai nút cố định: **"Nói lại"** và **"Gọi tình nguyện viên"** (escalate), cùng vị trí trên mọi màn hình.
4. Ngôn ngữ đời thường, không thuật ngữ (dùng `banned_terms` → từ thay thế trong `config/guardrails.yaml`); thông điệp lỗi khích lệ ("Không sao đâu bác, mình thử lại nhé"), không đếm ngược, không xếp hạng công khai.
5. Sandbox dựng theo bố cục ứng dụng thật nhưng **luôn có nhãn "Ứng dụng mô phỏng"** và dữ liệu giả từ `fake_data` của kịch bản; bước tiếp theo được đánh dấu bằng khung động; kèm cặp vẽ khung lên ảnh chụp.
6. Dashboard tình nguyện viên: bảng tiến độ và "3 người cần kèm hôm nay" ở đầu; báo cáo xuất PDF/XLSX.
7. PWA cài được; offline cho màn hình tĩnh (service worker cache kịch bản + câu sinh sẵn + clip TTS — ADR-006); hỏi đáp/kèm cặp cần mạng thì nói rõ.
8. Nhãn "nội dung do AI tạo" trên phản hồi và giọng nói tổng hợp (Luật AI); nút "Nguồn" mở trang chính thống cho câu có dữ kiện.

## Kiểm tra tự động (mỗi PR chạm UI)
- vitest: token cỡ chữ ≥ 20 pt, vùng bấm ≥ 56 px, tương phản ≥ 7:1 (đọc ngưỡng từ `config/app.yaml`), có "Nói lại"/"Gọi tình nguyện viên" trên mọi route, nhãn mô phỏng trên sandbox.
- Playwright e2e (`E2E=1 make e2e`) trên 3 viewport **360×800, 390×844, 412×915**; ảnh chụp mọi màn hình vào `docs/screens/YYYY-MM-DD/` để người dùng duyệt.
- axe: 0 lỗi nghiêm trọng; Lighthouse mobile ≥ 90 hiệu năng và a11y.
- Trước khi viết mã màn hình mới: 3 phương án bố cục bằng HTML thật + ảnh chụp để người dùng chọn (prompt.md D3).

## Cấm
Chữ < 20 pt · nút < 56 px · tương phản < 7:1 · CSS inline · thuật ngữ · hiển thị/lưu OTP, mật khẩu, số thẻ, CCCD (kể cả sandbox) · màn hình lừa đảo dạng kịch bản hoàn chỉnh (chỉ mẫu hành vi + nhãn "Đây là mô phỏng") · hard-code URL API.
