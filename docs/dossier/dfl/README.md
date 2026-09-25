# `docs/dossier/dfl/` — nguồn hồ sơ Data for Life 2026 (đề DA940-01)

Thư mục này chứa **nguồn** của hồ sơ dự thi Data for Life mùa 4 (Bộ Công an), theo ADR-007 (đề xuất, chờ người dùng
duyệt). Yêu cầu của Ban Tổ chức nằm ở `docs/competition/DFL-2026-yeu-cau.md`; về hồ sơ DFL, file đó là căn cứ.
Hồ sơ Bảng C cũ (`docs/dossier/src/`, `docs/dossier/README.md`) chỉ còn để lưu trữ.

## Hồ sơ gồm gì

| Thành phần (Thể lệ, Điều 6) | Nguồn trong repo | Ghi chú |
| --- | --- | --- |
| Phiếu đăng ký trực tuyến | `mo-ta-ngan.md` (Tên giải pháp, Mô tả ngắn, Năng lực đội, Tóm tắt kinh nghiệm) | Người dùng dán vào form trên dataforlife.vn |
| Bản đề xuất ≤ 10 trang, PDF, ≤ 10 MB | Các file nguồn của bản đề xuất (gói P7b) và `figures/*.png` | Số liệu đọc tự động từ `eval/reports/` |
| Video ≤ 3 phút (dạng link) | `video/loi-thoai.yaml`, `video/slides/*.html` | Chỉ quay tính năng chạy thật |
| Cam kết của mọi thành viên | `cam-ket.md` | Mỗi thành viên tự gõ chữ ký trên form |
| Link dùng thử | — | Không bắt buộc; để trống khi chưa có máy chủ công khai |

File phụ trợ:

- `checklist-nop.md`: các bước nộp theo giờ, dành cho người dùng.
- `thu-de-nghi-du-lieu.md`: thư xin Ban Tổ chức dữ liệu CSDL thủ tục hành chính cho vòng 2. Gửi hay không do người dùng quyết.
- `team-dfl.example.yaml`: mẫu thông tin đội. Bản thật đặt ở `docs/dossier/private/team-dfl.yaml` (đã gitignore). **Không ghi số điện thoại hay email** vào file này.

## Dựng hồ sơ

```bash
uv run python docs/dossier/build/build_dfl.py --draft   # bản nháp: giữ placeholder chưa có số liệu
uv run python docs/dossier/build/build_dfl.py           # bản chính thức: dừng nếu còn placeholder
# bản v2 (đang khuyến nghị nộp): thư mục riêng, bảng đội trống, thêm độ trễ chỉ-CPU
uv run python docs/dossier/build/build_dfl.py --out docs/dossier/out/dfl/v2   --team docs/dossier/out/dfl/team-dfl.blank.yaml --env eval/reports/latency-cpu-only.json
```

`--env eval/reports/latency-cpu-only.json` nạp số đo chỉ-CPU vào khóa `env.*` (bản đề xuất đọc
`env.latency_s.cpu_only.*` và `env.ablation_latency_s.template_only.cpu_only.p95`). Nếu bỏ cờ này, các ô đó hiện
"chưa đo", không có số giả.

Bản dựng nằm ở `docs/dossier/out/dfl/` (gitignore): PDF bản đề xuất, `mo-ta-ngan.filled.md` (đã thay số liệu) và
video. Nếu `build_dfl.py` chưa có, gói P7b hoặc P10 đang làm; tạm thời chưa dựng được.

## Bản nộp v2 (25/9/2026, khuyến nghị nộp)

Số liệu lấy từ lượt đo v2 (`eval/reports/latest.json` lúc 2026-09-25T07:34:35Z, `ablation-tthc.json`,
`latency-cpu-only.json`). Bảng đội vẫn để ô trống cho người dùng điền. Khác biệt so với v1, bảng số v1 → v2 và các
bước còn lại: `docs/dossier/out/dfl/v2/BAN-GIAO-v2.md`.

| File nộp | Đường dẫn | Ghi chú (`v2/build-report.json`, ffprobe) |
| --- | --- | --- |
| Bản đề xuất PDF | `docs/dossier/out/dfl/v2/de-xuat-giai-phap.pdf` | 9 trang, 591.646 byte, đủ 4 hình |
| Bản Word để sửa tay | `docs/dossier/out/dfl/v2/de-xuat-giai-phap.docx` | Điền đội và link rồi xuất lại PDF |
| Mô tả ngắn đã điền số | `docs/dossier/out/dfl/v2/mo-ta-ngan.filled.md` | Tên 140/400, Mô tả 1.909/2.000 ký tự |
| Cam kết | `docs/dossier/out/dfl/v2/cam-ket.docx` | Mỗi thành viên tự gõ chữ ký trên form |
| Video mp4 | `docs/dossier/out/dfl/v2/video/ctcv-dfl-2026.mp4` | 143,3 giây, 1920×1080, 4.614.380 byte; phụ đề in cứng, kèm `.srt` |

Bản v1 và v1.1 (`docs/dossier/out/dfl/`, `docs/dossier/out/dfl/v1_1/`, bàn giao ở `docs/dossier/out/dfl/BAN-GIAO.md`)
được giữ nguyên, không ghi đè.

## Luật viết

- Mọi con số phải lấy từ `eval/reports/latest.json`, `eval/reports/ablation-tthc.json`,
  `eval/reports/latency-cpu-only.json` hoặc `data/registry/`.
  Chưa có số thì dùng placeholder `{{eval:<khóa>|chưa đo}}`. Kế hoạch ghi rõ là "mục tiêu" hoặc "vòng 2".
- Thể lệ (Điều 7, 13) cấm làm giả kết quả và cấm trình diễn tính năng không tồn tại. Không nhắc giọng nói, pilot hay
  "đã triển khai" khi chưa có thật.
- Kê khai rõ ba phần: phần đội tự xây, phần AI hỗ trợ viết mã (Claude Code), phần kế thừa (mô hình trọng số mở,
  thư viện mã nguồn mở, dữ liệu công khai của Cổng Dịch vụ công Bộ Công an).
- Ba nguyên tắc bất biến, ghi đúng nguyên văn:
  1. Agent không có tool nào hành động trên hệ thống thật hay tài khoản thật; sandbox là hệ thống giả lập tách biệt.
  2. Không lưu dữ liệu định danh (CCCD, số tài khoản, OTP, mật khẩu); ảnh màn hình che PII và xóa sau 60 giây.
  3. Mọi dữ kiện đọc cho người dân phải có trích dẫn; không có nguồn thì trả lời "không chắc" và escalate.
