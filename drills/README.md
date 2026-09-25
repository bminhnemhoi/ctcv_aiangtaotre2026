# ctcv-drills — vắc-xin lừa đảo (kịch bản mức dấu hiệu)

Gói `ctcv_drills` (brief E01 §6, D27) giữ các kịch bản lừa đảo **ở mức mẫu hành vi**: một câu mô tả tình huống (`pretext`), **đúng một lượt** kẻ lừa đảo nói/nhắn (`utterance`, có nhãn "[Mô phỏng]"), các dấu hiệu (`red_flags`), 3–4 lựa chọn với đúng một lựa chọn đúng, `debrief` và "3 việc phải làm". Không file nào chứa lời thoại hoàn chỉnh nhiều lượt có thể sao chép để đi lừa người khác.

| Mô-đun | Vai trò |
| --- | --- |
| `schema.py` | Model Pydantic v2 `Drill` + enum `Channel`, `Impersonates`, `RedFlag`; sinh `config/schemas/drill.schema.json` qua `make schemas`. |
| `validator.py` | `validate(drill) -> list[Issue]` và `validate_data(raw)`/`validate_file(path)`: quy tắc D27 (xem dưới). |
| `validate.py` | CLI `python -m ctcv_drills.validate [file/thư mục…]`, mã thoát 1 khi có lỗi. |
| `scoring.py` | `grade(drill, option_id, seconds) -> Grade`, `vulnerability_score(list[Grade]) -> float` (0–100, càng cao càng dễ tổn thương) cho so sánh trước/sau. |
| `loader.py` | `list_drills()`, `load_drill(key, variant)`, `variants_of(key)`, `checksum(drill)`. |
| `rules.yaml` | Ngưỡng và danh sách chặn (số từ tối đa, mẫu URL/SĐT, tên ngân hàng/cơ quan thật, dấu hiệu nhiều lượt, tham số chấm điểm). |

## Quy tắc biên soạn (validator từ chối nếu vi phạm)

1. Không có trường `script`, `dialogue`, `message`, `transcript`, `turns`, `messages`, `conversation` ở bất kỳ cấp nào của JSON.
2. `utterance`: đúng một lượt, ≤ 40 từ, có nhãn "[Mô phỏng]", không xuống dòng, không dấu hiệu leo thang ("bước 2", "sau đó gửi"…).
3. Mọi chuỗi: ≤ 200 ký tự; không URL/tên miền, không số điện thoại, không dãy ≥ 6 chữ số (số tài khoản, số tiền viết bằng chữ: "hai trăm nghìn"), không tên ngân hàng/cơ quan thật (danh sách trong `rules.yaml`).
4. `pretext` ≤ 30 từ; `debrief` ≤ `max_sentences` câu và `debrief`/`three_things` không chứa `banned_terms` (config/guardrails.yaml).
5. `options` 3–4 mục, đúng một `correct: true`; `three_things` đúng 3 mục; `label` = "Đây là mô phỏng"; `variant` 1..5; `severity` 1..3.
6. Tên file: `<key>.json` cho biến thể 1, `<key>.v<n>.json` cho biến thể 2..5.

## Dùng nhanh

```bash
uv run python -m ctcv_drills.validate
uv run pytest drills --cov=ctcv_drills
```

```python
from ctcv_drills import load_drill, grade, vulnerability_score

drill = load_drill("gia-danh-cong-an-goi-dien")
before = grade(drill, "chuyen-tien", seconds=20)  # sai → score 0
after = grade(drill, "cup-may", seconds=8)  # đúng, nhanh → score 100
vulnerability_score([before]), vulnerability_score([after])  # 100.0, 0.0
```

Danh sách 20 kịch bản dự kiến: `scenarios/README.md`. `/v1/drills` chọn biến thể **phía server** và không có endpoint liệt kê (D27).

## Kiểm thử (`drills/tests/`)

| File | Kiểm tra gì |
| --- | --- |
| `test_schema.py` | Enum `channel`/`impersonates`/`red_flags` khớp brief §6, đúng một lựa chọn đúng, đúng 3 việc phải làm, nhãn cố định, `variant` 1..5, `severity` 1..3. |
| `test_validator.py` | Mẫu = 0 lỗi; mỗi file trong `fixtures/invalid/*.json` vi phạm **đúng một** quy tắc, tên file = mã lỗi; `forbidden-field.json` là kịch bản có lời thoại nhiều lượt và bị chặn trước cả bước schema (brief §15). |
| `test_scoring.py` | `grade()` 100 → 60 theo thời gian, sai = 0, lựa chọn lạ → lỗi có mã; `vulnerability_score()` có trọng số `severity`. |
| `test_rules.py`, `test_loader.py`, `test_cli.py` | `rules.yaml` khớp D27, nạp biến thể, checksum, mã thoát CLI. |
| `test_schema_file.py` | `config/schemas/drill.schema.json` phải bằng đúng kết quả `scripts/gen_schemas.py` (lệch → CI đỏ; chạy `make schemas`). |

Các file trong `tests/fixtures/invalid/` cố ý chứa link giả, số giả (có dấu cách) và tên thật để kiểm tra bộ chặn — không dùng làm bài luyện.
