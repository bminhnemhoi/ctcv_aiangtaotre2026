# ctcv-sandbox — máy trạng thái kịch bản mô phỏng

Gói `ctcv_sandbox` (brief E01 §5) gồm:

| Mô-đun | Vai trò |
| --- | --- |
| `schema.py` | Model Pydantic v2 (`Scenario`, `Screen`, `Element`, `TapAction`/`InputAction`, `Mistake`, `Success`); sinh `config/schemas/scenario.schema.json` qua `make schemas`. |
| `validator.py` | `validate(scenario) -> list[Issue]`: kiểm tra cấu trúc (đến được, màn hình kết thúc, hành động trỏ đúng, câu hướng dẫn ≤ 2 câu, không thuật ngữ, ô nhạy cảm). Mỗi `Issue` có mã máy (`Code`) và thông điệp tiếng Việt. |
| `validate.py` | CLI `python -m ctcv_sandbox.validate [file/thư mục…]`, mã thoát 1 khi có lỗi. |
| `engine.py` | `start(scenario) -> State`, `apply(scenario, state, event) -> (State, Feedback)`; không gọi model; đếm `steps/mistakes/hints_used`; giá trị ô nhạy cảm không bao giờ được lưu. |
| `events.py` | `SessionEvent` (tap/input/back/ask) và `to_stream_record()` cho Redis Stream — không mang giá trị người dùng gõ (D28). |
| `loader.py` | `list_scenarios()`, `load_scenario(id)`, `checksum(scenario)` (SHA-256 JSON chuẩn hóa). |

## Dùng nhanh

```bash
uv run python -m ctcv_sandbox.validate                # kiểm tra mọi kịch bản
uv run pytest sandbox --cov=ctcv_sandbox              # test + coverage
uv run python scripts/gen_schemas.py                  # cập nhật JSON Schema
```

```python
from ctcv_sandbox import load_scenario, start, apply, SessionEvent

scenario = load_scenario("chuyen-khoan-qr")
state = start(scenario)
state, feedback = apply(scenario, state, SessionEvent.tap("btn_promo"))
feedback.mistake, feedback.say  # True, "Đó là quảng cáo, bác bấm nút xanh có chữ Quét QR nhé."
```

## Ngưỡng và danh sách

Không có ngưỡng nào ghi cứng trong mã: số câu tối đa và thuật ngữ bị cấm đọc từ `config/guardrails.yaml` (`max_sentences`, `banned_terms`); hai mục bắt buộc của `never_ask` (`otp`, `mat_khau`) là quy tắc của brief §5.

Cách viết kịch bản mới và danh sách 12 kịch bản: xem `scenarios/README.md`.

## Kiểm thử (`sandbox/tests/`)

| File | Kiểm tra gì |
| --- | --- |
| `test_schema.py` | Enum (5 nhóm kỹ năng khớp `config/app.yaml`), slug, `level` 1..3, nhãn "mô phỏng", `never_ask` bắt buộc có `otp` + `mat_khau`, cấm trường lạ. |
| `test_validator.py` | Kịch bản mẫu = 0 lỗi; mỗi file trong `fixtures/invalid/*.json` vi phạm **đúng một** quy tắc và tên file (kebab) = mã lỗi (`start-screen-missing.json` → `START_SCREEN_MISSING`). |
| `test_engine.py` | Đi trọn `chuyen-khoan-qr` (đường đúng, đường sai có gợi ý, nhập sai, nút lạ, back/ask), giá trị ô nhạy cảm bị che, không sửa state đầu vào. |
| `test_events.py` | `SessionEvent` và bản ghi Redis Stream không mang giá trị người dùng gõ. |
| `test_loader.py`, `test_cli.py` | `load_scenario`/`list_scenarios`/`checksum`, mã thoát CLI (0/1), phát hiện id trùng. |
| `test_schema_file.py` | `config/schemas/scenario.schema.json` phải bằng đúng kết quả `scripts/gen_schemas.py` (lệch → CI đỏ; chạy `make schemas`). |

Các file trong `tests/fixtures/invalid/` cố ý chứa lỗi (kể cả ô OTP không đánh dấu) để kiểm tra validator — không dùng làm kịch bản thật.
