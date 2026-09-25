# `eval/sets/samples/` — mẫu đánh giá được commit

Thư mục này chứa các tập đánh giá nhỏ được commit vào repo (tập lớn nằm ngoài repo, gitignore). Hai tệp dưới đây
dùng cho bộ `qa` của `make eval` với kho thủ tục hành chính (TTHC) của Cổng Dịch vụ công Bộ Công an
(hợp đồng C8, ADR-007). Mỗi dòng theo lược đồ `qa_tthc.schema.json`.

## Hai tệp TTHC

| Tệp | Cách tạo | Nội dung |
| --- | --- | --- |
| `qa_tthc.jsonl` | Sinh tất định từ bản ghi bằng mẫu câu (`source: "generated:tthc-template/1"`) | Câu hỏi đúng mục (`kind: field`) về phí, thời hạn, giấy tờ, có bản bỏ dấu |
| `qa_tthc_handwritten.jsonl` | Đội soạn tay (`source: "handwritten:qa-tester"`) | Câu hỏi khó hơn theo 8 loại dưới đây |

**Nguồn gốc câu hỏi (ghi trung thực):** câu hỏi do đội soạn (có hỗ trợ AI), **không phải câu hỏi thật của người
dân**. Chúng mô phỏng cách người cao tuổi hỏi (khẩu ngữ, phương ngữ Trung và Nam, gõ không dấu hoặc gõ sai) nhưng
chưa được kiểm chứng với người dùng thật; kết quả trên tập này không thay cho thử nghiệm với người dân. Câu hỏi viết
bằng chữ, chưa có giọng nói.

### Loại câu trong `qa_tthc_handwritten.jsonl` (83 dòng)

| `kind` | Số câu | `expect` | Mục đích |
| --- | --- | --- | --- |
| `colloquial` | 26 | `answer` | Khẩu ngữ ("làm lại cái căn cước", "nhập hộ khẩu", "phạt nguội") |
| `dialect` | 12 | `answer` | Phương ngữ Trung ("mần", "răng", "chi", "mô") và Nam ("tui", "hông", "nhiêu") |
| `no_diacritics` | 11 | `answer` | Không dấu, thiếu dấu, gõ sai ("tạm chú", "mấtt", "bao nhiu") |
| `out_of_kb` | 10 | `refuse_or_escalate` | Thủ tục có thật nhưng không thuộc kho Bộ Công an (kết hôn, khai sinh, sổ đỏ...) |
| `out_of_domain` | 8 | `refuse_or_escalate` | Ngoài chủ đề (giá vàng, thời tiết, bóng đá, thuốc...) |
| `sensitive` | 6 | `refuse_or_escalate` | Xin OTP, mật khẩu, số thẻ, ảnh căn cước — **không chứa chữ số** |
| `real_action` | 5 | `refuse_or_escalate` | Đòi làm thay trên ứng dụng hoặc tài khoản thật |
| `injection` | 5 | `refuse_or_escalate` | Chèn lệnh điều khiển, không chứa dữ liệu định danh |

Quy tắc soạn:

- `gold_procedure_id` là `procedure_id` thật trong `data/clean/tthc/records/`. Khi cùng một thủ tục có nhiều cấp
  (xã, tỉnh, trung ương), chọn cấp người dân hay gặp và ghi các mã cùng tên vào `notes`.
- `expected_values` chép nguyên văn từ bản ghi (ví dụ `"20.000"`, `"08 Ngày làm việc"`, `"CT01"`). Nguồn ghi mơ hồ,
  mâu thuẫn giữa các cấp hoặc không có số thì để `[]`. Nguồn ghi "Chưa quy định" hoặc "Không" thì hệ thống không được
  tự đưa ra số tiền.
- Câu `out_of_kb` đã được đối chiếu với tên của mọi bản ghi trong kho lúc soạn (25/9/2026). Một số câu cố ý chứa từ
  có trong thân bản ghi khác (khai sinh, ly hôn, chứng thực kèm căn cước) để thử cổng chặn.
- Không đưa dãy từ 9 chữ số trở lên, số điện thoại, số CCCD hay mã OTP dạng số vào câu hỏi
  (`tests/invariants/test_no_pii.py` quét thư mục này). Tấn công cần chuỗi giống dữ liệu định danh nằm ở `eval/redteam/`.

## Chia dev/test

- `qa_tthc_handwritten.jsonl`: dòng `h-NNN` vào `dev` khi `NNN` chia hết cho 3, còn lại vào `test`
  (27 dev / 56 test).
- `qa_tthc.jsonl`: vào `dev` khi `int(sha256(id), 16) % 10 < 3`.

**Chỉ hiệu chỉnh ngưỡng, từ đồng nghĩa, cụm phương ngữ và prompt trên tập `dev`.** Không dùng tập `test` để chỉnh
ngưỡng hay sửa câu cho khớp hệ thống; số liệu báo cáo (hồ sơ, `eval/reports/latest.json`) lấy trên tập `test`. Khi
một câu `test` lộ lỗi, thêm câu hồi quy tương tự vào `dev` rồi mới sửa hệ thống, không sửa câu `test`.

## Kiểm tra

```bash
uv run pytest tests/invariants/test_no_pii.py -q
```

Kết quả thử trực tiếp qua API thuộc báo cáo đánh giá, nằm trong `eval/reports/`, không nằm ở đây.
