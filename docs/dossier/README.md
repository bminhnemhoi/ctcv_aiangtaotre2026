# `docs/dossier/` — hồ sơ dự thi Bảng C (Cầm Tay Chỉ Việc)

Thư mục này chứa mọi thứ để sinh 6 thành phần hồ sơ mà BTC yêu cầu (xem `docs/competition/BTC-2026-yeu-cau.md`
— file đó thắng mọi tài liệu khác về hồ sơ). Tuyến đăng ký: **qua trường** (TDTU gửi danh sách trước 30/9/2026);
hồ sơ sơ bộ chiếm **40%** điểm vòng khu vực, hackathon 2 ngày (10–11/10) chiếm 60%.

## 1. Sáu thành phần BTC → lệnh sinh

| # | Thành phần BTC | File đầu ra (`docs/dossier/out/`) | Lệnh | Việc của người |
| --- | --- | --- | --- | --- |
| 1 | Tài liệu dự án PDF ≤ 20 trang theo MẪU 3 | `01_TaiLieuDuAn_CTCV.docx` → `.pdf` | `make dossier DRAFT=1` (nháp) / `make dossier` (chính thức) = `uv run python docs/dossier/build/build_dossier.py [--draft]` | Điền `private/team.yaml`, soát 13 file `src/`, ký khối "Đại diện đội thi" |
| 2 | Video thuyết trình ≤ 5 phút | `02_VideoThuyetTrinh.mp4` | Kịch bản `video/thuyet-trinh-5-phut.md` + `video/slide-outline.md` | Quay (2 lần), dựng, kiểm tra ≤ 300 s |
| 3 | Video demo ≤ 5 phút | `03_VideoDemo.mp4` | Storyboard `video/demo-5-phut.md` (Playwright ghi màn hình trên bản đã tag) | Quay 1 cảnh người thật, thuyết minh |
| 4 | Giấy xác nhận sinh viên (cả 3) | `04_XacNhanSV_<i>.pdf` | — | Xin tại Phòng CTSV (3–7 ngày), quét |
| 5 | Link kho mã nguồn | `05_Repo.txt` | Tag `{{team:repo_tag}}`, bật public đúng ngày nộp | Kiểm tra README chạy 1 lệnh, LICENSE, SECURITY.md |
| 6 | Bản kê khai công cụ AI, dữ liệu, API, thư viện, phần tự xây | `06_KeKhaiAI.md` (→ PDF) | `make declaration` = `uv run python scripts/declaration.py` (đọc `data/registry/*.yaml`, `uv.lock`, `package.json`, `docs/prompt-log/INDEX.md`) | Ký xác nhận |
| — | Prompt Log (bắt buộc kèm hồ sơ; mục 13 MẪU 3 đòi link Google Drive) | `07_PromptLog.zip` + Drive | `make promptlog-sync` (nhập transcript thiếu) → `make promptlog-export` = `uv run python scripts/promptlog_export.py` (kiểm hash, gitleaks + regex PII, redaction) → `make evidence` (ảnh minh chứng theo ngày) | Tải lên Drive, mở quyền, dán link vào `team.yaml` |

Khi `Makefile` chưa có target tương ứng, chạy lệnh `uv run …` trong cột "Lệnh".

## 2. Cấu trúc thư mục

```
docs/dossier/
  README.md                 # file này
  src/00-thong-tin-doi.md   # giải thích nơi lưu thông tin đội (không vào hồ sơ)
  src/01-…13-….md           # 13 mục MẪU 3, H1 nguyên văn tên mục, blockquote "Nội dung trình bày" của mẫu
  build/build_dossier.py    # điền mẫu → docx (+ PDF nếu có LibreOffice); build/md2docx.py; build/tests/
  figures/                  # PNG/MMD cho hình (README hướng dẫn render mermaid)
  private/team.example.yaml # mẫu thông tin đội; private/team.yaml là bản thật (gitignore)
  video/                    # kịch bản thuyết trình, storyboard demo, dàn ý 12 slide
  out/                      # sản phẩm sinh ra (gitignore)
```

## 3. Ánh xạ 13 mục MẪU 3 ↔ nguồn nội dung ↔ ngân sách từ

Ngân sách tính bằng số token cách nhau bởi khoảng trắng (âm tiết tiếng Việt) trong phần thân mục (không tính H1,
blockquote hướng dẫn, khối mermaid, dòng ảnh). Script cảnh báo khi vượt +10%, test dừng khi vượt. Ước tính trang =
tổng từ / 450 + 1 trang thông tin đội; mục tiêu tổng **6.500–7.500** từ → ≤ 18 trang, chừa chỗ cho hình.

| # | Tên mục (nguyên văn MẪU 3) | File | Nguồn trong `docs/idea.md` | Ngân sách |
| --- | --- | --- | --- | --- |
| 1 | Bài toán hoặc vấn đề thực tiễn cần giải quyết | `01-bai-toan.md` | §1, §2 | 550 |
| 2 | Mục tiêu, phạm vi và đối tượng ứng dụng của sản phẩm | `02-muc-tieu-pham-vi.md` | §1, §3, §4 | 550 |
| 3 | Dữ liệu sử dụng, nguồn dữ liệu và tính hợp lệ của dữ liệu | `03-du-lieu.md` | §7 (bảng nguồn, giấy phép đã sửa theo brief D7/D10) | 600 |
| 4 | Quy trình tiền xử lý, làm sạch, chuẩn hóa hoặc tổ chức dữ liệu | `04-tien-xu-ly.md` | §7 (pipeline, kiểm định) + F12 | 550 |
| 5 | Thuật toán, mô hình, phương pháp hoặc công cụ trí tuệ nhân tạo được sử dụng | `05-mo-hinh.md` | §5, §6 + D8/D9/F06/F08 | 650 |
| 6 | Quy trình huấn luyện, tinh chỉnh, tích hợp hoặc khai thác mô hình (nếu có) | `06-huan-luyen.md` | §6 (đã làm / kế hoạch) + F04 | 660 |
| 7 | Chỉ số, phương pháp hoặc tiêu chí đánh giá kết quả | `07-chi-so-danh-gia.md` | §8 + F05/F07/F13, pilot hai tầng | 600 |
| 8 | Kết quả thử nghiệm, phân tích ưu điểm, hạn chế và khả năng mở rộng | `08-ket-qua.md` | §8 — mọi số là `{{eval:…}}`; mục "Kết quả chưa đạt" bắt buộc | 800 |
| 9 | So sánh với phương án hoặc mô hình cơ sở, phân tích đóng góp của các thành phần trong hệ thống (nếu có) | `09-so-sanh.md` | §6 (ablation), §8 (baseline chatbot tổng quát) + ablation tắt guardrail đã đo | 660 |
| 10 | Kiến trúc hệ thống và phương án triển khai | `10-kien-truc-trien-khai.md` | §5, §10 + CF-07 (hai tầng phục vụ) | 650 |
| 11 | Phân tích rủi ro, yêu cầu bảo mật, đạo đức trí tuệ nhân tạo và an toàn dữ liệu | `11-rui-ro-bao-mat.md` | §9, §14 + SEC-01…06, LEG-11 | 750 |
| 12 | Hướng phát triển, hoàn thiện và khả năng ứng dụng trong thực tiễn | `12-huong-phat-trien.md` | §10, §13 (lịch 3 pha ADR-006) | 500 |
| 13 | Lịch sử câu lệnh và hình ảnh minh chứng quá trình phát triển sản phẩm từ bản nháp đến khi hoàn thiện | `13-lich-su-cau-lenh.md` | Prompt log + Drive (D12, D20, D21) | 300 |

Tổng ngân sách: **7.820** (bản 19/9/2026: đếm trang thật bằng Word = xem `out/dossier-report.json`; giới hạn BTC 20 trang). Số hiện tại: chạy `make dossier DRAFT=1`
để xem bảng; test `test_word_budget_respected` dừng khi một mục vượt +10% hoặc tổng vượt 7.820.

## 4. Quy tắc trung thực (plan §10, prompt.md D6)

1. **Không đưa số chưa đo.** Mọi số liệu ở mục 6, 8, 9 là `{{eval:<khóa>}}` và chỉ được thay từ
   `eval/reports/latest.json` (`make eval`/`make pilot-report`) và `eval/reports/engineering.json`
   (`uv run python scripts/collect_engineering_metrics.py` — số kỹ thuật không cần mô hình). Cú pháp
   `{{eval:<khóa>|chưa đo}}` in đúng chữ dự phòng khi chưa có số (trung thực, không chặn xuất);
   `{{eval:<khóa>}}` trần vẫn thành `⟪CHƯA ĐO⟫` và chặn bản chính thức. Chạy lại script đo ngay trước
   `make dossier` để số trong hồ sơ khớp bản gắn tag.
2. **Mục "Kết quả chưa đạt" là bắt buộc** (8.4) và phải nói thẳng chỗ yếu: chưa fine-tune, WER giọng địa phương,
   quy mô thử nghiệm nhỏ, hạng mục hoãn (APK, kèm cặp app thật, YOLOX).
3. **Ảnh màn hình là ảnh thật của bản được gắn tag nộp** (N15: v1.0 = bản nộp tuyến trường), lấy từ
   `docs/screens/<ngày>/` do `make evidence` chụp; không mock, không ảnh của tính năng chưa có.
4. **Phần AI hỗ trợ được kê khai đúng như Prompt Log**; không sửa tay log hay lịch sử commit (BTC nghiêm cấm).
5. **Số hiệu văn bản pháp luật** chỉ được giữ trong bản chính thức khi có `verified_on` trong `docs/legal/refs.yaml`
   (LEG-11); một thành viên người tra cứu, không giao Claude. Đã xác minh 18/9: 134/2025/QH15, 142/2026/NĐ-CP;
   chưa xác minh: 05/2026/TT-BKHCN, 91/2025/QH15, 356/2025/NĐ-CP.
6. **Kế hoạch ≠ kết quả:** mục 6 và 9 đánh dấu rõ "đã làm" / "kế hoạch (Pha D)"; hàng "Đã làm" ở 6.1 chỉ giữ khi
   epic tương ứng đã merge và có test/số đo trước tag nộp, nếu không thì đổi thành "kế hoạch" trước khi `make dossier`.
7. **Giấy phép đúng sự thật:** PhoWhisper BSD-3-Clause, YOLOX-Tiny Apache-2.0 (không Ultralytics), Qwen3.5-2B (không
   có 1.7B), VIVOS CC BY-NC-SA chỉ đánh giá.

## 5. Bước Google Drive (mục 13 MẪU 3, CF-03)

1. `make promptlog-sync` rồi `make promptlog-export`: kiểm hash INDEX, chạy gitleaks + regex PII; phát hiện → thay
   `[REDACTED-SECRET sha256:<8>]`, ghi INDEX/README (chính sách công bố, không sửa log).
2. `make evidence`: chụp ảnh ứng dụng theo ngày vào `docs/screens/YYYY-MM-DD/` + snapshot `DAILY.md`.
3. Tạo thư mục Drive theo cấu trúc trong `src/13-lich-su-cau-lenh.md` (`01-prompt-log/` … `07-prompt-cong-cu-khac/`),
   tải lên: `07_PromptLog.zip` giải nén, `docs/prompt-log/system/`, `docs/prompt-log/subagents/`, `docs/screens/`,
   ADR + eval reports, ZIP mã nguồn tại tag, prompt template sinh dữ liệu/judge, các phiên `pre-D1/` xuất tay.
4. Chia sẻ "Bất kỳ ai có liên kết — Người xem", mở thử bằng cửa sổ ẩn danh, dán link vào `private/team.yaml
   → lien_ket.drive_url`, chạy lại `make dossier`.
5. **Không** đưa lên Drive: `private/team.yaml`, dữ liệu pilot thô, ảnh có dữ liệu cá nhân, `.env`.

## 6. Checklist D-2 (trước hạn nội bộ của trường; plan §15 điều chỉnh theo lịch thật)

- [ ] Hỏi Đoàn trường/Phòng CTSV: hạn nội bộ, ai upload 6 thành phần, BTC có cho cập nhật hồ sơ trước chung kết (N02).
- [ ] 3 thành viên cùng trường, ≤ 22 tuổi, cam kết có mặt 10–11/10 và 20–22/11; `private/team.yaml` khớp giấy xác nhận SV.
- [ ] Tag bản nộp, CI xanh (`make check`), repo public, LICENSE Apache-2.0, SECURITY.md, README chạy 1 lệnh.
- [ ] URL công khai + trang status xanh ≥ 24 giờ; tầng luôn bật (CPU) đã bật để URL sống đến chung kết (CF-07).
- [ ] `eval/reports/latest.json` do `make eval`/`make pilot-report` sinh; `make dossier` (chính thức) chạy xanh: 0 dấu
      `⟪…⟫`, 0 số hiệu chưa xác minh, PDF ≤ 20 trang (đếm trang thật: LibreOffice nếu có, nếu không thì Microsoft Word qua COM trên Windows).
- [ ] Hình `figures/*.png` đã render (mermaid-cli, biểu đồ pilot), ảnh từ `docs/screens/`.
- [ ] 2 video ≤ 300 s, có tên đội và tên sản phẩm ở đầu, không lộ dữ liệu người dùng, chỉ tính năng có trong bản tag.
- [ ] `06_KeKhaiAI` khớp `uv.lock`/`package.json`/registry; nêu rõ mô hình sinh dữ liệu và Claude Code.
- [ ] `07_PromptLog.zip` hash khớp INDEX; Drive đã mở quyền, link trong PDF mục 13 mở được từ tài khoản khác.
- [ ] Giấy xác nhận SV đủ 3 người; khối ký "Đại diện đội thi" đã ký.
- [ ] Nộp đúng cổng/hạn, lưu biên nhận; commit `docs/prompt-log/` cùng ngày.
