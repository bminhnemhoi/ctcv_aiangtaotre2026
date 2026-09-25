# Kịch bản vắc-xin lừa đảo (`drills/scenarios/*.json`)

Mỗi file là **một biến thể** của một kịch bản lừa đảo, viết ở **mức mẫu hành vi** (idea §4, plan §7 bước 7, brief §6 + D27): một câu mô tả tình huống, đúng một lượt kẻ lừa đảo nói/nhắn có nhãn "[Mô phỏng]", dấu hiệu nhận biết, 3–4 lựa chọn (đúng một lựa chọn an toàn), lời giải thích và "3 việc phải làm". **Không** có lời thoại nhiều lượt, không link, không số điện thoại/tài khoản, không tên ngân hàng/cơ quan thật.

- Schema: `config/schemas/drill.schema.json` (sinh từ `ctcv_drills.schema.Drill` bằng `make schemas`).
- Kiểm tra: `uv run python -m ctcv_drills.validate` (mã thoát 1 khi có lỗi). Mọi file mới phải được **duyệt tay 100 %** trong PR.
- Tên file: `<key>.json` (biến thể 1), `<key>.v2.json` … `<key>.v5.json`.
- Nguồn: cảnh báo công khai của Bộ Công an / Hiệp hội An ninh mạng — chỉ lấy mẫu hành vi, không sao chép nguyên văn.

## 20 kịch bản dự kiến (khóa `key`; chỉ khóa, không kịch bản)

| # | `key` | Tình huống (idea §4) | `channel` gợi ý | `impersonates` gợi ý | Giao |
| --- | --- | --- | --- | --- | --- |
| 1 | `gia-danh-cong-an-goi-dien` | mạo danh công an | call | `cong-an` | **E01** (mẫu, biến thể 1 — đã có) |
| 2 | `gia-danh-co-quan-thue` | mạo danh thuế | zalo | `thue` | E09-lite |
| 3 | `gia-danh-ngan-hang-khoa-the` | mạo danh ngân hàng | sms | `ngan-hang` | E09-lite |
| 4 | `shipper-giao-hang-chuyen-khoan` | shipper | call | `shipper` | E09-lite |
| 5 | `thong-bao-trung-thuong` | trúng thưởng | sms | `trung-thuong` | E09-lite |
| 6 | `nguoi-than-muon-tien` | người thân mượn tiền | zalo | `nguoi-than` | E09-lite |
| 7 | `dien-luc-doa-cat-dien` | điện lực | call | `dien-luc` | E09-lite |
| 8 | `buu-dien-buu-pham-vi-pham` | bưu điện | call | `buu-dien` | E09-lite |
| 9 | `viec-nhe-luong-cao` | việc nhẹ lương cao | zalo | *(cần mở rộng enum — ADR ở E09)* | E09-lite |
| 10 | `dau-tu-loi-nhuan-cao` | đầu tư | zalo | *(cần mở rộng enum — ADR ở E09)* | E09 |
| 11 | `con-cap-cuu-chuyen-vien-phi` | con cấp cứu | call | `nguoi-than` | E09 |
| 12 | `khoa-sim-nang-cap` | khóa SIM | call | *(cần mở rộng enum — ADR ở E09)* | E09 |
| 13 | `cap-nhat-cccd-qua-link` | cập nhật CCCD | zalo | `cong-an` | E09 |
| 14 | `nhan-qua-tu-nuoc-ngoai` | nhận quà | zalo | `buu-dien` | E09 |
| 15 | `vay-online-phi-giai-ngan` | vay online | zalo | `ngan-hang` | E09 |
| 16 | `ma-qr-la` | mã QR lạ | zalo | `ngan-hang` | E09 |
| 17 | `link-gia-ngan-hang` | link giả | sms | `ngan-hang` | E09-lite |
| 18 | `mao-danh-toa-an-trieu-tap` | mạo danh tòa án | call | *(cần mở rộng enum — ADR ở E09)* | E09 |
| 19 | `cap-nhat-sinh-trac-hoc` | xác thực sinh trắc học | call | `ngan-hang` | E09 |
| 20 | `hoan-tien-don-hang` | hoàn tiền | zalo | `shipper` | E09 |

E09-lite (Pha A): 10 kịch bản × 1 biến thể; Pha D: 20 kịch bản × 5 biến thể (`variant` 1..5, `severity` 1..3). Bốn khóa đánh dấu *(cần mở rộng enum)* cần thêm nhãn `impersonates` (tuyển dụng, đầu tư, nhà mạng, tòa án) qua ADR trước khi viết — enum hiện tại giữ đúng 8 nhãn của brief §6.

## Mã dấu hiệu (`red_flags`)

`giuc-chuyen-tien` · `doi-otp` · `xung-co-quan` · `link-la` · `doa-dam` · `yeu-cau-cai-app` · `giu-bi-mat` · `tai-khoan-la`

## Quy tắc chặn (validator)

Xem `drills/README.md` mục "Quy tắc biên soạn". Tóm tắt: không trường `script`/`dialogue`/`message`/`transcript`/`turns`; `utterance` một lượt ≤ 40 từ có "[Mô phỏng]"; không URL/SĐT/dãy ≥ 6 chữ số/tên thật ở bất kỳ chuỗi nào; chuỗi ≤ 200 ký tự; `pretext` ≤ 30 từ; `debrief` ≤ 2 câu; đúng một lựa chọn đúng; đúng 3 việc phải làm.
