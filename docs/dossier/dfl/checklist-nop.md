# Checklist nộp hồ sơ Data for Life 2026 — ngày 25/9/2026

Form nộp ghi hạn **25/09/2026** nhưng không ghi giờ (`docs/competition/DFL-2026-yeu-cau.md` §0, §1.2).
**Hãy nộp sớm, tốt nhất xong trước 12:00.** Đừng chờ đến tối: thể lệ, trang chủ và báo chí ghi các ngày khác nhau, và
hồ sơ nộp sau hạn thì không hợp lệ (Điều 6).

## Quyết định chờ anh/chị

- [ ] **Duyệt ADR-007** (`docs/decisions/ADR-007-chuyen-huong-data-for-life.md` và phụ lục `ADR-007-hop-dong.md`):
  đổi cuộc thi, route thứ 17 `/v1/coach/intake-check`, chế độ demo cho đăng nhập, `config/rag.yaml` ánh xạ tên model
  Ollama. Sau khi nộp, ghi "chốt" vào mục Trạng thái (hoặc báo orchestrator).
- [ ] **Cho phép sửa 2 dòng CLAUDE.md** để nguồn sự thật về hồ sơ trỏ sang `docs/competition/DFL-2026-yeu-cau.md`.
- [ ] **Ba lỗi nền của cổng audit** (`docs/decisions/ADR-008-vong-2-dfl-va-cong-audit.md`), chọn cho từng lỗi:
  (a) áp `allowed-deps` đã ghép sẵn; (b) thêm `# gitleaks:allow` cho fixture trong `.claude/hooks/tests`;
  (c) tạm bỏ qua GHSA vite 5 hay nâng lên vite ≥ 6.4.3. Nên quyết **trước 06:00**.
- [ ] **Xác nhận điều khoản sử dụng của nguồn dữ liệu:** một thành viên (là người, không phải AI) mở
  dichvucong.bocongan.gov.vn, đọc dòng chân trang "ghi rõ nguồn khi sử dụng lại", rồi báo orchestrator ghi
  `tos_checked_on: 2026-09-25` vào `data/sources.yaml` và registry.
- [ ] **Duyệt mục nguồn mới trong `data/sources.yaml`** (Cổng Dịch vụ công Bộ Công an, khoảng 110 thủ tục trên 9 trang
  danh sách là mục tiêu crawl). Mục này đang ở dạng đề xuất, theo quy trình E03.

## Theo giờ

### Ngay bây giờ
- [ ] (5 phút) Trả lời 3 câu hỏi mở: phạm vi crawl; duyệt ADR-007 và sửa 2 dòng CLAUDE.md; 3 lỗi nền cổng audit.
- [ ] (Khuyến nghị) Tạo commit đầu tiên để có điểm quay lui trước khi các agent chạy song song:
  `git add -A && git commit -m "[E01] khung dự án CTCV"`. Theo CLAUDE.md, anh/chị tự tạo commit này.

### Trước 06:00
- [ ] Quyết 3 lỗi nền cổng audit (xem mục "Quyết định chờ anh/chị"). Quyết định sẽ ghi vào ADR-008.
- [ ] Xác nhận điều khoản sử dụng nguồn dữ liệu (xem trên).

### Sáng sớm: tạo hồ sơ và đội
- [ ] Vào dataforlife.vn/tham-gia-cuoc-thi, bấm **"Bắt đầu đăng ký"**. Lưu lại email và mật khẩu. **Email không sửa
  được sau khi tạo.**
- [ ] Nhập đội **từ 3 người trở lên** (trang chủ ghi 3–10 thành viên). Đội trưởng **đủ 18 tuổi** và **bắt buộc có
  link GitHub hoặc portfolio**.
- [ ] Mỗi người điền: họ tên, ngày sinh, email, số điện thoại (9–12 số), trình độ, vai trò, tóm tắt kinh nghiệm
  ≤ 500 ký tự (mẫu ở `docs/dossier/dfl/mo-ta-ngan.md`). Thông tin này chỉ gõ trên form, không ghi vào repo.
- [ ] Tạo `docs/dossier/private/team-dfl.yaml` theo mẫu `docs/dossier/dfl/team-dfl.example.yaml` (họ tên, vai trò,
  trình độ, năng lực, link video và repo; **không ghi SĐT hay email**) để PDF có bảng đội và liên kết.
- [ ] Tạo repo GitHub (riêng tư, hoặc công khai nếu muốn giám khảo xem mã) và push; lấy link cho ô portfolio của đội
  trưởng. Nếu công khai: kiểm tra lại rằng repo **không có** `.env` và `docs/dossier/private/`.

### Khoảng 08:00: duyệt bản dựng
- [ ] Duyệt PDF `docs/dossier/out/dfl/de-xuat-giai-phap.pdf`: **tối đa 10 trang, tối đa 10 MB**, định dạng PDF, không
  có số liệu bịa, thông tin đội đúng.
- [ ] Xem video `docs/dossier/out/dfl/video/ctcv-dfl-2026.mp4` (tối đa 3 phút). Tùy chọn: thu âm lời thuyết minh theo
  `docs/dossier/dfl/kich-ban-video.md`, rồi nhờ devops ghép bằng `--voice`.
- [ ] Tải video lên YouTube (chế độ **Không công khai**) hoặc Google Drive (**"Bất kỳ ai có đường liên kết đều xem
  được"**). Mở thử bằng cửa sổ ẩn danh.

### Trước 12:00: điền form và nộp
- [ ] Chọn đề: **"Bài toán Cơ quan nhà nước" → nhóm Trí tuệ nhân tạo → DA940-01**.
- [ ] Dán **Tên giải pháp** (≤ 400 ký tự) và **Mô tả ngắn** (≤ 2.000 ký tự) từ
  `docs/dossier/out/dfl/mo-ta-ngan.filled.md`. Đếm lại ký tự trước khi dán.
- [ ] Tải PDF bản đề xuất lên; dán link video.
- [ ] Link sản phẩm dùng thử: **để trống** (chưa có máy chủ công khai; mục này không bắt buộc).
- [ ] **Mọi thành viên gõ chữ ký** cam kết trên form (nội dung thư ở `docs/dossier/dfl/cam-ket.md`).
- [ ] Xem trang **/preview**, kiểm tra từng mục.
- [ ] Bấm **"Gửi hồ sơ dự thi" TRƯỚC 12:00 NGÀY 25/9**.
- [ ] **Chụp màn hình xác nhận** và lưu bản sao mọi file đã nộp.

### Sau khi nộp
- [ ] Tùy chọn: gửi thư `docs/dossier/dfl/thu-de-nghi-du-lieu.md` cho Ban Tổ chức để xin dữ liệu CSDL thủ tục hành
  chính cho vòng 2; ghi lại ngày gửi.
- [ ] Ghi "chốt" vào ADR-007 (hoặc báo orchestrator) và cho phép sửa 2 dòng CLAUDE.md.
- [ ] Theo dõi thông báo vòng 2. Vòng 2 có thể bắt đầu từ 25/9 (theo thể lệ) hoặc 28/9 (theo trang chủ); xem ADR-008.
- [ ] Không tự công bố kết quả trước Ban Tổ chức (Điều 12).
