# Hướng dẫn hoàn tất và nộp hồ sơ Bảng C — Cầm Tay Chỉ Việc

Cập nhật 19/9/2026. Tài liệu dành cho ba thành viên đội. Mọi lệnh chạy trong **Git Bash** tại gốc repo.
Yêu cầu chính thức của BTC: `docs/competition/BTC-2026-yeu-cau.md`. Tuyến đăng ký: **qua trường**, trường gửi danh
sách trước **30/9/2026** — hỏi Đoàn trường/Phòng CTSV hạn nội bộ và ai là người upload lên cổng BTC.

## 1. Bộ hồ sơ gồm gì và đang ở đâu

| # | Thành phần BTC | File | Trạng thái 19/9 |
| --- | --- | --- | --- |
| 1 | Tài liệu dự án PDF ≤ 20 trang theo MẪU 3 | `docs/dossier/out/01_TaiLieuDuAn_CTCV.pdf` (+ `.docx`) | **Xong bản nháp 15–16 trang**; còn thiếu thông tin đội, link Drive, link repo (mục 2) |
| 2 | Video thuyết trình ≤ 5 phút | kịch bản `docs/dossier/video/thuyet-trinh-5-phut.md`, 12 slide `slide-outline.md` | Có kịch bản; quay sau khi có bản chạy được (Pha A) |
| 3 | Video demo ≤ 5 phút | storyboard `docs/dossier/video/demo-5-phut.md` | Có storyboard; quay trên bản gắn tag |
| 4 | Giấy xác nhận sinh viên (cả 3 người) | `docs/dossier/out/04_XacNhanSV_<tên>.pdf` | **Việc của đội**: nộp đơn tại Phòng CTSV ngay (3–7 ngày làm việc) |
| 5 | Link kho mã nguồn | `docs/dossier/out/05_Repo.txt` | Tạo repo GitHub `ctcv`, commit đầu tiên, bật public đúng ngày nộp |
| 6 | Bản kê khai công cụ AI, dữ liệu, API, thư viện, phần tự xây | `docs/dossier/out/06_KeKhaiAI.pdf` | **Xong** (sinh tự động; chạy lại trước khi nộp) |
| — | Prompt Log (bắt buộc; mục 13 MẪU 3 đòi link Google Drive công khai) | `docs/dossier/out/07_PromptLog.zip` + thư mục Drive | Hook đang tự ghi; đóng gói bằng lệnh ở mục 3 |

## 2. Ba việc chỉ con người làm được (khoảng 30 phút)

1. **Điền thông tin đội.** Chép `docs/dossier/private/team.example.yaml` thành `docs/dossier/private/team.yaml` rồi điền
   đúng như giấy xác nhận sinh viên: họ tên, ngày sinh, lớp–ngành–khoa–trường, xã/phường–tỉnh, điện thoại, email của
   từng người; tên đội trưởng ở `ky_ten.dai_dien`. File này đã nằm trong `.gitignore`, **không** commit, không đưa lên Drive.
2. **Tạo thư mục Google Drive** theo 7 thư mục con ghi ở mục 13 của hồ sơ (`01-prompt-log` … `07-prompt-cong-cu-khac`),
   chia sẻ "Bất kỳ ai có liên kết — Người xem", mở thử bằng cửa sổ ẩn danh, dán link vào `team.yaml → lien_ket.drive_url`.
   Nhớ xuất các hội thoại AI đã dùng để soạn ý tưởng/kế hoạch (17/9) vào `docs/prompt-log/pre-D1/` và đưa lên Drive.
3. **Tạo repo GitHub** và dán link vào `team.yaml → lien_ket.repo_url` (tag nộp: `v1.0-dossier`). Nếu đã có URL ứng dụng
   công khai thì điền `app_url`, `status_url`; chưa có thì để nguyên — hồ sơ tự ghi "chưa công bố".

## 3. Lệnh sinh bộ hồ sơ (chạy theo thứ tự)

```bash
export PATH="$HOME/.local/bin:$HOME/AppData/Roaming/npm:$PATH" PYTHONUTF8=1

# (a) Đo lại số liệu thật ngay trước khi xuất — hồ sơ chỉ in số do lệnh đo sinh ra
uv run python -m ctcv_eval.redteam                 # red-team 50 kịch bản (không cần mô hình)
uv run python -m ctcv_eval.harness --quick         # ghi eval/reports/latest.json
uv run python -m ctcv_eval.redteam.ablation        # ablation "tắt guardrail"
uv run python scripts/collect_engineering_metrics.py   # test, coverage, số kịch bản, route, web

# (b) Bản nháp để soát (có dấu "BẢN NHÁP" nếu chưa có team.yaml)
uv run python docs/dossier/build/build_dossier.py --draft

# (c) Bản chính thức — chỉ xuất khi đủ: team.yaml, link Drive + repo, không còn dấu ⟪…⟫, văn bản luật đã xác minh
uv run python docs/dossier/build/build_dossier.py

# (d) Bản kê khai và Prompt Log
uv run python scripts/declaration.py
uv run python docs/dossier/build/md_to_pdf.py docs/dossier/out/06_KeKhaiAI.md
bash .claude/hooks/run.sh promptlog --sync          # nhập phiên Claude Code còn thiếu
uv run python scripts/promptlog_export.py           # ZIP + SHA-256 + kiểm tra bí mật/PII
```

PDF được xuất bằng Microsoft Word có sẵn trên máy (đếm trang chính xác); script báo số trang và dừng nếu > 20.

## 4. Soát lần cuối trước khi nộp

- [ ] Khối thông tin đội khớp giấy xác nhận SV; đánh dấu đúng "3 người"; đội trưởng ký tay vào khối "Đại diện đội thi"
      trên bản in (hoặc chèn chữ ký vào PDF), ghi ngày tháng.
- [ ] Đọc lại 13 mục: mọi câu "Đã làm" đều đúng với bản gắn tag; bảng 6.1, 8.1, 8.2, 9.2 phản ánh số đo mới nhất.
      Khi có thêm kết quả (RAG, giọng nói, thử nghiệm 5–10 người), chỉ cần chạy lại mục 3 — ô "chưa đo" tự thay bằng số.
- [ ] Một thành viên đọc toàn văn 5 văn bản pháp luật ở mục 11.3 và ghi số điều/khoản vào `docs/legal/refs.yaml`
      (số hiệu và ngày hiệu lực đã được đối chiếu nguồn chính thức ngày 18–19/9).
- [ ] Link Drive và repo mở được từ tài khoản khác; repo có LICENSE, SECURITY.md, README chạy một lệnh.
- [ ] Hai video ≤ 300 giây, có tên đội và tên sản phẩm ở đầu, chỉ nói về tính năng có thật trong bản tag.
- [ ] Không có thông tin cá nhân của thành viên hay người học trong repo/Drive (trừ PDF hồ sơ).
- [ ] Nộp đúng cổng, đúng hạn của trường; lưu biên nhận; commit `docs/prompt-log/` cùng ngày.

## 5. Nguyên tắc trung thực (BTC nghiêm cấm làm giả Prompt Log và lịch sử commit)

Hồ sơ không chứa số ước lượng: số kỹ thuật đọc từ `eval/reports/engineering.json`, số có mô hình và người thật đọc từ
`eval/reports/latest.json`; chỉ số chưa đo được in đúng là "chưa đo" kèm thời điểm dự kiến. Mục 8.4 "Kết quả chưa đạt" là
bắt buộc. Không sửa tay `docs/prompt-log/`.
