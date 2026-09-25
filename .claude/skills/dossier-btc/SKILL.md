---
name: dossier-btc
description: Sinh và kiểm hồ sơ dự thi Bảng C theo yêu cầu BTC — 6 thành phần và 13 mục MẪU 3, PDF ≤ 20 trang, 2 video ≤ 5 phút, bản kê khai AI, prompt log ZIP + Google Drive. Chỉ gọi tay bằng /dossier-btc.
argument-hint: "[DRAFT=1 | final | check]"
disable-model-invocation: true
---
# /dossier-btc $ARGUMENTS — hồ sơ BTC (nguồn thắng mọi tài liệu khác: `docs/competition/BTC-2026-yeu-cau.md`)

Giao cho `docs-writer` (nội dung), `qa-tester` (kiểm số liệu), `reviewer` (đọc như giám khảo). Chế độ: `DRAFT=1` (nháp, cho phép placeholder) · `final` (0 placeholder, số hiệu pháp luật đã `verified_on`) · `check` (chỉ kiểm, không sinh).

## Sáu thành phần (trang /ho-so) → `docs/dossier/out/`
| # | Thành phần | File | Lệnh | Người dùng làm |
| --- | --- | --- | --- | --- |
| 1 | Tài liệu dự án **PDF ≤ 20 trang theo MẪU 3** | `01_TaiLieuDuAn_CTCV.docx/.pdf` | `make dossier [DRAFT=1]` | điền `docs/dossier/private/team.yaml`, ký |
| 2 | Video thuyết trình ≤ 5 phút | `02_VideoThuyetTrinh.mp4` | kịch bản `docs/dossier/video/thuyet-trinh-5-phut.md` + slide outline | quay, dựng |
| 3 | Video demo ≤ 5 phút | `03_VideoDemo.mp4` | storyboard `docs/dossier/video/demo-5-phut.md` (Playwright ghi màn hình bản đã tag) | quay cảnh người thật |
| 4 | Giấy xác nhận SV **tất cả** thành viên | `04_XacNhanSV_<i>.pdf` | — | xin Phòng CTSV (3–7 ngày) |
| 5 | Link kho mã / file mã | `05_Repo.txt` | tag `v1.0`, public đúng ngày | kiểm README chạy 1 lệnh, LICENSE, SECURITY.md |
| 6 | **Bản kê khai** công cụ AI, dataset, API, thư viện, mã nguồn mở, phần tự xây | `06_KeKhaiAI.md/.pdf` | `make declaration` (registry + lockfile + INDEX prompt log) | ký |
| — | Prompt Log (bắt buộc; mục 13 đòi link Drive) | `07_PromptLog.zip` + `drive/` | `make promptlog-sync` → `make promptlog-export` (hash + gitleaks + PII redaction D21) → `make evidence` | upload Drive, mở quyền "Anyone with link – Viewer", dán link vào `team.yaml` |

## 13 mục MẪU 3 (H1 nguyên văn, đúng thứ tự; file `docs/dossier/src/NN-*.md`; ngân sách từ trong `docs/dossier/README.md`)
1. Bài toán hoặc vấn đề thực tiễn cần giải quyết (idea §1–2) · 2. Mục tiêu, phạm vi và đối tượng ứng dụng của sản phẩm (idea §1, 3, 4) · 3. Dữ liệu sử dụng, nguồn dữ liệu và tính hợp lệ của dữ liệu (idea §7, registry, giấy phép) · 4. Quy trình tiền xử lý, làm sạch, chuẩn hóa hoặc tổ chức dữ liệu (plan §7) · 5. Thuật toán, mô hình, phương pháp hoặc công cụ trí tuệ nhân tạo được sử dụng (idea §5–6, `config/models.yaml`) · 6. Quy trình huấn luyện, tinh chỉnh, tích hợp hoặc khai thác mô hình (nếu có) (idea §6, `training/reports`) · 7. Chỉ số, phương pháp hoặc tiêu chí đánh giá kết quả (idea §8, `config/eval.yaml`) · 8. Kết quả thử nghiệm, phân tích ưu điểm, hạn chế và khả năng mở rộng (`eval/reports`, `eval/pilot/report.md`, **"kết quả chưa đạt" bắt buộc**) · 9. So sánh với phương án hoặc mô hình cơ sở, phân tích đóng góp của các thành phần trong hệ thống (nếu có) (`training/reports/ablation.md`) · 10. Kiến trúc hệ thống và phương án triển khai (idea §5, 10; URL + status page) · 11. Phân tích rủi ro, yêu cầu bảo mật, đạo đức trí tuệ nhân tạo và an toàn dữ liệu (idea §9, 14; `docs/legal/refs.yaml`) · 12. Hướng phát triển, hoàn thiện và khả năng ứng dụng trong thực tiễn (idea §10, 13; ADR-006 lộ trình chung kết) · 13. Lịch sử câu lệnh và hình ảnh minh chứng quá trình phát triển sản phẩm từ bản nháp đến khi hoàn thiện (link Drive `{{team:drive_url}}`, `docs/screens/`).
Phần thông tin đội (họ tên, ngày sinh, lớp/ngành/khoa/trường, xã/phường, điện thoại, email) chỉ từ `docs/dossier/private/team.yaml` (gitignore; Claude không đọc/ghi) → placeholder `{{team:<key>}}`.

## Quy tắc trung thực (BTC nghiêm cấm làm giả Prompt Log / lịch sử commit)
- Mọi số truy vết về `eval/reports/*`, `eval/pilot/report.md`, `docs/status/last_check.json`; placeholder `{{eval:<key>}}` khi chưa có; script so khớp số PDF ↔ báo cáo = 0 sai lệch.
- Kê khai rõ ba phần: **tự xây / AI hỗ trợ / kế thừa mã nguồn mở**; API thương mại (nếu dùng ở bước sinh dữ liệu) phải kê khai; không ghi "tự làm chủ" cho phần dùng API.
- Ảnh màn hình là ảnh thật của bản được tag; hồ sơ ghi trạng thái tại ngày nộp + lộ trình chung kết; số hiệu văn bản pháp luật chỉ khi `verified_on` (LEG-11).
- Prompt log: không sửa tay; redaction chỉ trong bản công bố (`[REDACTED-SECRET sha256:<8>]`), ghi `REDACTIONS.md`; bản gốc + hash INDEX giữ nguyên. Drive không chứa `private/`, `.env`, dữ liệu pilot thô.

## Quy trình
1. `make promptlog-sync && make docs-check`; `docs-writer` rà 13 file `src/` theo ngân sách từ, hình ở `docs/dossier/figures/`.
2. `make dossier DRAFT=1` → đếm trang (≤ 20), placeholder còn lại, cảnh báo pháp lý; `final`: 0 placeholder, `make declaration`, `make promptlog-export`, `make evidence`.
3. `qa-tester`: so khớp số liệu, video ≤ 300 s, checksum ZIP khớp INDEX. `reviewer`: đọc PDF như giám khảo, 10 câu phản biện + câu trả lời (khác gì ChatGPT; người cao tuổi dùng được không; thay TNV không; dữ liệu ở đâu; an toàn lừa đảo ngược; fine-tune thắng base bao nhiêu; chi phí tự host; phần đội tự xây; lộ trình).
4. Kết thúc ≤ 15 dòng: file đã sinh, số trang, placeholder/việc người dùng phải làm tay (quay, ký, upload Drive, giấy xác nhận SV), rủi ro hạn nộp (tuyến trường 30/9 — ADR-006).
