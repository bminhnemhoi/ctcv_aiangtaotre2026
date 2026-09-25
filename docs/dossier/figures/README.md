# `docs/dossier/figures/` — hình cho Tài liệu dự án

| File PNG cần có | Nguồn | Cách tạo |
| --- | --- | --- |
| `04-pipeline-du-lieu.png` | `04-pipeline-du-lieu.mmd` (xuất tự động từ khối mermaid trong `src/04-tien-xu-ly.md`) | `npx -y @mermaid-js/mermaid-cli -i docs/dossier/figures/04-pipeline-du-lieu.mmd -o docs/dossier/figures/04-pipeline-du-lieu.png -w 1600 -b white` |
| `10-kien-truc.png` | `10-kien-truc.mmd` (từ `src/10-kien-truc-trien-khai.md`) | như trên, đổi tên file |
| `08-pilot-truoc-sau.png` | `make pilot-report` (biểu đồ trước/sau từ `eval/pilot/report.md`) | copy PNG từ `eval/pilot/` vào đây |

Quy tắc: sửa sơ đồ trong file `.md` (nguồn duy nhất), chạy `build_dossier.py --draft` để cập nhật `.mmd`, rồi render
lại PNG. Ảnh chụp màn hình sản phẩm lấy từ `docs/screens/<ngày>/` (sinh bởi `make evidence`) — chỉ ảnh thật của
bản được gắn tag nộp; không dùng mock.
