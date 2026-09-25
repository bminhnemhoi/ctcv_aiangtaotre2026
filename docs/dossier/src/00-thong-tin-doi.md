# 00. Thông tin đội thi — dữ liệu nằm ở đâu và được điền thế nào

File này **không** được đưa vào hồ sơ; nó chỉ giải thích cách khối "thông tin đội" của MẪU 3 (Bảng C) được điền.

## Nguồn dữ liệu

- Thông tin cá nhân của ba thành viên (họ tên, ngày sinh, lớp/ngành/khoa/trường, xã/phường, điện thoại, email)
  nằm trong `docs/dossier/private/team.yaml` — file này bị **gitignore** và không bao giờ vào repo công khai,
  Google Drive hay phiên Claude Code (brief D25; phát hiện N09).
- Bản mẫu có chỗ trống là `docs/dossier/private/team.example.yaml` (được commit). Người dùng chép thành
  `team.yaml` rồi điền; chỉ con người điền file này.

## Cách khối thông tin được điền vào mẫu

`docs/dossier/build/build_dossier.py` mở `docs/template/AI2026_Mau_ho_so.docx`, giữ lại phần MẪU 3 (Bảng C),
rồi ghi vào bảng 22 dòng × 4 cột của mẫu:

| Dòng trong mẫu | Khóa trong `team.yaml` |
| --- | --- |
| Số lượng thí sinh trong đội thi (1/2/3 người) | `so_luong_thi_sinh` → ô tương ứng được đánh dấu ☒ |
| Họ và tên | `thi_sinh[i].ho_ten` |
| Ngày/tháng/năm sinh | `thi_sinh[i].ngay_sinh` |
| Lớp hành chính, ngành, khoa, trường | `thi_sinh[i].lop_nganh_khoa_truong` |
| Xã/phường/đặc khu, tỉnh/thành phố | `thi_sinh[i].xa_phuong_tinh` |
| Điện thoại | `thi_sinh[i].dien_thoai` |
| Email | `thi_sinh[i].email` |

Ngoài bảng, script chèn một dòng "Tên sản phẩm: Cầm Tay Chỉ Việc (CTCV)" dưới tiêu đề mẫu (mẫu không có ô tên
sản phẩm), thay `{{team:drive_url}}`, `{{team:repo_url}}`, `{{team:repo_tag}}`, `{{team:app_url}}`,
`{{team:status_url}}` trong mục 10 và 13 bằng `lien_ket.*`, và điền khối ký cuối trang từ `ky_ten.*`.

## Chế độ nháp và chế độ chính thức

- `--draft`: thiếu `team.yaml` → dùng `team.example.yaml` và in dấu "BẢN NHÁP — DỮ LIỆU MẪU" ở đầu tài liệu.
- Chính thức (không `--draft`): thiếu `team.yaml`, còn giá trị `<...>` chưa điền, còn số chưa đo `⟪CHƯA ĐO⟫`,
  còn hình chưa có, hoặc còn số hiệu văn bản pháp luật chưa xác minh trong `docs/legal/refs.yaml` → script dừng,
  không xuất file.

## Việc con người phải làm trước khi nộp

1. Chốt danh sách 3 thành viên cùng trường, ≤ 22 tuổi, cam kết có mặt 10–11/10 và 20–22/11/2026 (BTC không cho
   thay người sau đăng ký).
2. Điền `team.yaml` đúng như giấy xác nhận sinh viên (thành phần hồ sơ số 4).
3. Ký tay vào khối "Đại diện đội thi" trên bản in (hoặc chèn chữ ký ảnh vào PDF) sau khi `make dossier` xong.
