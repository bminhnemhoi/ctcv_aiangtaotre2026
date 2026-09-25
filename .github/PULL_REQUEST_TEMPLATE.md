<!-- Tiêu đề PR: [E0X] mô tả ngắn (Conventional Commits, plan §3). Nhánh: epic/E0X-ten-ngan. -->

## 1. Làm gì

<!-- Phạm vi theo epics/E0X.md (mục Công việc). Liệt kê thay đổi chính, ADR mới/sửa, config/*.yaml đã đổi. -->

-

## 2. Test thế nào

<!-- Lệnh đã chạy và kết quả (make check QUICK=1 trên máy dev; CI check.yml; make gate nếu cần GPU → gắn nhãn `needs-gpu`). Dán số test/coverage, đường dẫn eval/reports nếu có. -->

- `make check QUICK=1`: …
- Test nghiệm thu của epic (`uv run pytest <path>`): …

## 3. Checklist cho người dùng (≤ 30 phút)

<!-- Việc người dùng tự thử trên điện thoại/máy thật trước khi duyệt; sao chép từ mục "Checklist cho người dùng" của epic. -->

- [ ] …
- [ ] …

## 4. Rủi ro

<!-- Điều gì có thể hỏng, cách quay lui (make rollback TAG=…), câu hỏi mở còn chờ người dùng, phạm vi cố tình chưa làm. -->

-

---

## Definition of Done (plan §14 Phụ lục B — Claude Code tự tick trước khi mở PR)

- [ ] Test nghiệm thu trong epic xanh trong CI; `make check` xanh.
- [ ] Không test nào bị xóa hay bỏ qua để cho xanh; coverage không giảm.
- [ ] Ba nguyên tắc bất biến (chỉ sandbox · không hỏi OTP/mật khẩu · trích dẫn + escalate) có test bảo vệ và vẫn xanh.
- [ ] README mô-đun, CHANGELOG, ADR (nếu có) cập nhật; DAILY.md cập nhật.
- [ ] Prompt log của phiên đã ghi và có trong `docs/prompt-log/INDEX.md`.
- [ ] PR có đủ 4 mục: làm gì, test thế nào, checklist ≤ 30 phút cho người dùng, rủi ro.
- [ ] Không thêm phạm vi ngoài mục 2 của docs/plan.md; không thêm thư viện chưa có trong `config/allowed-deps.yaml` (D26).
- [ ] Cấu hình mới có test schema; không secret trong mã; log không PII.
- [ ] Đổi model / schema DB / ngưỡng eval (điểm dừng bắt buộc) đã được người dùng chốt trong ADR trước khi merge.
