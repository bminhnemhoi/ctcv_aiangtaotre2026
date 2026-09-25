# docs/legal — Danh mục văn bản pháp luật và cổng xác minh (LEG-11)

## Vì sao có thư mục này
`docs/idea.md` §9 nêu 5 văn bản (Luật 134/2025/QH15, NĐ 142/2026/NĐ-CP, TT 05/2026/TT-BKHCN, Luật 91/2025/QH15, NĐ 356/2025/NĐ-CP) với ngày hiệu lực cụ thể, nhưng rà soát 18/9 (`docs/analysis/2026-09-18-review-findings.md`, LEG-11) chỉ xác minh được **hai** văn bản đầu; ba văn bản còn lại **chưa xác minh** là có tồn tại với đúng số hiệu. Trích dẫn sai số hiệu vào PDF nộp BTC là lỗi không sửa được sau khi nộp.

## Cách dùng `refs.yaml`
- Mỗi mục: `id`, `so_hieu`, `ten`, `ngay_ban_hanh`, `hieu_luc`, `dieu_khoan_ap_dung`, `url` (vbpl.vn / chinhphu.vn / congbao.chinhphu.vn), `verified_on` (YYYY-MM-DD), `verified_by` (tên thành viên **người** đã đọc toàn văn), `ghi_chu`.
- `verified_on` rỗng = **chưa xác minh** → số hiệu đó không được xuất hiện trong PDF, video, bản kê khai.
- Trạng thái 18/9: đã xác minh số hiệu + ngày hiệu lực của `134/2025/QH15` (01/03/2026) và `142/2026/NĐ-CP` (01/05/2026) — nhưng **điều khoản cụ thể** (tiêu chí phân loại rủi ro của NĐ 142) vẫn phải được một thành viên đọc toàn văn và ghi số điều/khoản vào `dieu_khoan_ap_dung` trước khi viết mục 11.

## Cổng tự động
- `make dossier` (không `DRAFT=1`): `docs/dossier/build/build_dossier.py` quét PDF tìm mọi chuỗi dạng `NN/YYYY/QH15`, `NN/YYYY/NĐ-CP`, `NN/YYYY/TT-…`; mỗi số hiệu phải khớp một mục có `verified_on` không rỗng, nếu không → **fail** và in danh sách số hiệu vi phạm (DOSSIER.md, test nghiệm thu).
- `make dossier DRAFT=1`: chỉ cảnh báo.
- `uv run pytest tests/config` (khi gói J thêm schema `config/schemas/legal-refs.schema.json`): `refs.yaml` qua schema; `verified_on` phải là ngày ≤ hôm nay.

## Việc của người (không giao Claude)
1. Trước 27/9 (`make dossier` lần 1): một thành viên tra cứu 3 văn bản chưa xác minh; điền `url`, `hieu_luc`, `dieu_khoan_ap_dung`, `verified_on`, `verified_by`; nếu TT 05/2026/TT-BKHCN không tồn tại → thay bằng văn bản khung đạo đức AI đang hiệu lực hoặc xóa khỏi hồ sơ.
2. Đọc điều khoản phân loại rủi ro của NĐ 142/2026 và ghi căn cứ cụ thể cho "rủi ro thấp" (hỗ trợ học tập, không ra quyết định về quyền lợi) vào `dieu_khoan_ap_dung`; mục 11 hồ sơ dẫn đúng điều/khoản.
3. Không sửa `docs/idea.md` §9 (D31); ghi kết quả tra cứu vào đây và errata nếu số hiệu khác.
