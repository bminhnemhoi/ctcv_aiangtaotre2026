# ctcv-vision — dịch vụ ảnh màn hình (nhận diện phần tử, đọc màn hình, che PII, TTL 60 s)

Gói `ctcv-vision` (import `ctcv_vision`) nhận ảnh màn hình **ứng dụng mô phỏng**, tìm nút/ô nhập (YOLOX-Tiny ONNX, Apache-2.0 — không Ultralytics, D7), nhờ VLM (`config/models.yaml: vlm`, prompt `vlm_screen.v1`) trả trạng thái màn hình có cấu trúc, che vùng số nhạy cảm **trước khi lưu** và xóa ảnh sau `screen_ttl_seconds` (60 s, ADR-005). **E01 chỉ dựng khung**: `/health` chạy thật, `POST /detect` và `POST /screen` trả `501 NOT_IMPLEMENTED` tiếng Việt cho tới E08 (`epics/E08.md`); hai helper thuần Python (`redact`, `ttl`) đã chạy thật và có test.

## Đường dẫn

| Method | Path | E01 | Ghi chú |
| --- | --- | --- | --- |
| GET | `/health` | thật | `{status, service, version, checks{ui_detector, vlm, screen_store}, models{ui_detector, vlm}, screen_ttl_seconds}` |
| POST | `/detect` | 501 | multipart `image` → `DetectOut{boxes[{cls,x,y,w,h}], model}` (E08) |
| POST | `/screen` | 501 | multipart `image` → `ScreenOut{screen_state, step_text, boxes[]}` (E08) |

Cổng: `config/app.yaml: ports.vision` (8030). Lỗi thống nhất `{"error": {"code", "message"}}`; thiếu file → `422 VALIDATION_FAILED`. `boxes` không bao giờ chứa trường text (brief §4 `boxes_json`).

## Helper thuần Python (đã có, không cần thư viện ảnh)

- `ctcv_vision.redact.mask_regions(boxes, image_size, *, padding_px=0, normalised=None)` → `list[MaskRegion]`: nhận khung `{cls?,x,y,w,h}` / `{bbox:[…]}` / `(x,y,w,h)` / `(cls,x,y,w,h)`, tọa độ chuẩn hóa 0–1 (quy ước `bbox` của prompt VLM) hoặc pixel; nới `padding_px`, kẹp vào ảnh, bỏ khung rỗng, **gộp khung chồng nhau** để không lọt số giữa hai khung. `MaskRegion.to_dict()` ra đúng khuôn `boxes_json`.
- `ctcv_vision.redact.apply_mask(pixels, regions, fill)`: tô vùng lên lưới điểm ảnh 2 chiều (dùng cho test và mock).
- `ctcv_vision.redact.redact_digits_in_text(text, *, min_digits=4)`: chạy regex PII của `config/guardrails.yaml` (`ctcv_core.logging.scrub_pii`) rồi che mọi dãy số ≥ `min_digits` chữ số (kể cả có khoảng trắng/chấm/gạch giữa các nhóm) bằng `redaction_token`. Ngưỡng 4 theo E08/SEC-05, sẽ chuyển vào `guardrails.yaml` ở E08.
- `ctcv_vision.ttl.is_expired(created_at, ttl_s, *, now=None)`, `expires_at`, `seconds_left`, `default_ttl_seconds()` (= `screen_ttl_seconds`); datetime naive được coi là UTC; `ttl_s ≤ 0` → `ValueError`.

## Cấu hình

| Nguồn | Khóa | Ghi đè bằng env |
| --- | --- | --- |
| `config/models.yaml` | `models.ui_detector` (`yolox-tiny`, ngưỡng), `models.vlm` (id, ngưỡng, prompt) | `VLM_MODEL` |
| `config/app.yaml` | `screen_ttl_seconds`, `ports.vision` | `SCREEN_TTL_SECONDS`, `VISION_PORT` |

## Chạy và kiểm thử

```bash
uv run ctcv-vision                                    # uvicorn trên cổng ports.vision
uv run pytest services/vision --cov=ctcv_vision        # test + coverage
uv run ruff check services/vision && uv run ruff format --check services/vision
```

## Phụ thuộc nặng (E08)

`onnxruntime`, `opencv-python-headless`, `pillow` được ghi dưới `[project.optional-dependencies] runtime` trong `pyproject.toml` ở dạng **chú thích** — chưa cài ở E01. Khi E08 mở: bỏ chú thích, thêm vào `config/allowed-deps.yaml` (D26), `uv sync --package ctcv-vision --extra runtime`. Không bao giờ thêm `ultralytics`/`yolov5` (AGPL).

## Không được làm (E08)

Nhận/lưu ảnh app thật; cho VLM trả text tự do hoặc chép số từ màn hình; lưu ảnh quá `screen_ttl_seconds`; thêm OCR khi chưa có ADR + allow-list.
