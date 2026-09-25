# Thư mục `docs/dossier/private/` — dữ liệu cá nhân của đội (không vào repo)

- `team.example.yaml` — bản mẫu, được commit. Chỉ chứa chỗ trống `<...>`.
- `team.yaml` — bản thật, **gitignore** (`.gitignore` dòng `docs/dossier/private/*`). Chép từ bản mẫu và điền:
  số lượng thí sinh, sáu trường của từng thí sinh đúng như MẪU 3 (Bảng C), các liên kết Drive/repo/app, khối ký.
- `build_dossier.py` đọc `team.yaml`; nếu thiếu, chế độ `--draft` dùng `team.example.yaml` và in dấu
  "DỮ LIỆU MẪU" lên bản nháp; chế độ chính thức dừng với lỗi.

Quy tắc (brief D25, phát hiện N09): không dán nội dung `team.yaml` vào phiên Claude Code, không đưa file này lên
Google Drive (Drive chỉ chứa PDF đã điền), không gửi qua chat. Khi cần sửa thông tin đội, sửa trực tiếp file và
chạy lại `make dossier`.
