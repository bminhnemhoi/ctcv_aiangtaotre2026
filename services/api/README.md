# ctcv-api — dịch vụ API của CTCV

Gói `ctcv-api` (import `ctcv_api`) là cửa ngõ HTTP của hệ thống: xác thực (JWT ngắn hạn, 3 vai),
lớp học, phiên sandbox, hỏi–đáp có căn cứ, vắc-xin lừa đảo, báo cáo. Hợp đồng API là
`docs/plan.md` §5 và `docs/decisions/E01-brief.md` §3; schema dữ liệu là brief §4.

Hợp đồng có **17 route** `/v1`: 16 route của brief §3 và `POST /v1/coach/intake-check` do
ADR-007 (dự thi Data for Life 2026, đề DA940-01) thêm vào. Route **thật**: `GET /v1/scenarios`,
`/health`, `/metrics`, `POST /v1/coach/ask`, `POST /v1/coach/intake-check`; `/v1/auth/join` và
`/v1/auth/login` chạy thật **chỉ ở chế độ demo** (mục bên dưới). Các route còn lại trả
`501 NOT_IMPLEMENTED` kèm thông điệp tiếng Việt nêu rõ epic sẽ hiện thực.

## Chạy

```bash
uv sync --all-packages                       # cài toàn bộ workspace (một lần)
cp .env.example .env                         # điền JWT_SECRET, DATABASE_URL… (không commit)
uv run ctcv-api                              # uvicorn, cổng lấy từ config/app.yaml: ports.api
# hoặc
uv run uvicorn ctcv_api.main:create_app --factory --reload --port 8000
```

Biến môi trường được đọc bởi `ctcv_api.settings.Settings` (pydantic-settings, file `.env`):

| Biến | Mặc định (dev) | Ý nghĩa |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+pysqlite:///./ctcv-dev.db` | Chuỗi kết nối SQLAlchemy (prod: PostgreSQL 16) |
| `REDIS_URL`, `QDRANT_URL` | rỗng | Chưa cấu hình → `/health` báo `skipped` |
| `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_SCREENS` | rỗng / `screens` | Kho ảnh màn hình (TTL 60 s) |
| `JWT_SECRET` | `dev-only-change-me-not-for-production-use` | ≥ 32 byte; bắt buộc đổi khi `CTCV_ENV=prod` **hoặc khi bật demo** (v2, red-team F-08) |
| `JWT_TTL_MINUTES` | `config/app.yaml: jwt_ttl_minutes` | Hạn token |
| `RATE_LIMIT_PER_MIN`, `MAX_CONCURRENT_SESSIONS` | theo `config/app.yaml` | Bảo vệ tải (middleware ở E11) |
| `SCREEN_TTL_SECONDS`, `LOG_RETENTION_DAYS` | theo `config/app.yaml` | Chính sách dữ liệu |
| `CORS_ORIGINS` | suy từ `ports.web` + `APP_DOMAIN` | Danh sách origin, phân cách bằng dấu phẩy |
| `SCENARIOS_DIR` | `sandbox/scenarios` | Ghi đè thư mục kịch bản (dùng trong test) |
| `CTCV_DEMO_QR_TOKEN` | rỗng (tắt) | Mã QR lớp demo, ≥ 16 ký tự; **cấm ở prod** |
| `CTCV_DEMO_STAFF_PASSWORD` | rỗng (tắt) | Mật khẩu cán bộ demo, ≥ 12 ký tự; **cấm ở prod** |
| `CTCV_OLLAMA_BASE_URL` | `config/rag.yaml: serving.endpoint` | Máy chủ model cục bộ (Ollama) cho `/coach/ask` |
| `CTCV_RAG_COMPOSE_MODE` | `config/rag.yaml: compose_mode` | `template_only` = dự phòng, không gọi LLM |

## Các endpoint (prefix `/v1`, JSON, `Authorization: Bearer <JWT>`)

| Method | Đường dẫn | Vai | Trạng thái |
| --- | --- | --- | --- |
| POST | `/v1/auth/join` | người dân | 501 — E10; **demo** khi đặt `CTCV_DEMO_QR_TOKEN` |
| POST | `/v1/auth/login` | TNV / cán bộ | 501 — E10; **demo** khi đặt `CTCV_DEMO_STAFF_PASSWORD` |
| POST | `/v1/classes` | TNV | 501 — E10 |
| GET | `/v1/classes/{class_id}/progress` | TNV / cán bộ | 501 — E10 |
| GET | `/v1/reports/class/{class_id}?format=pdf\|xlsx` | TNV / cán bộ | 501 — E10 |
| GET | `/v1/scenarios?skill=&level=` | mọi vai | **thật** — đọc `sandbox/scenarios/*.json` |
| POST | `/v1/sessions` | người dân | 501 — E02 |
| POST | `/v1/sessions/{session_id}/events` | người dân | SSE, 1 sự kiện `NOT_IMPLEMENTED` — E02 |
| POST | `/v1/speech/asr` | mọi vai | 501 — E04 |
| POST | `/v1/speech/tts` | mọi vai | 501 — E04 |
| POST | `/v1/coach/ask` | người dân | **thật** — hỏi thủ tục hành chính có trích dẫn (ADR-007) |
| POST | `/v1/coach/intake-check` | TNV / cán bộ | **thật** — danh mục giấy tờ đã nhận / còn thiếu (ADR-007) |
| POST | `/v1/coach/screen` | người dân / TNV | 501 — E08 |
| POST | `/v1/drills` | người dân | 501 — E09 |
| POST | `/v1/drills/{drill_id}/answers` | người dân | 501 — E09 |
| GET | `/v1/health`, `/health` | hệ thống | **thật** — `{status, version, checks{db, redis, qdrant}}` |
| GET | `/v1/metrics`, `/metrics` | hệ thống | **thật** — Prometheus (`http_requests_total`, …) |

Không có endpoint liệt kê toàn bộ drill (D27): server tự chọn biến thể khi `POST /v1/drills`.

### Hỏi thủ tục hành chính (`POST /v1/coach/ask`, ADR-007 C6)

- Vào: `AskIn{question (1..500 ký tự), session_id? (≤ 64 ký tự — v2, red-team F-10)}`; `user_id` chỉ lấy từ JWT (D28).
- Ra: `AskOut{answer (≤ 2 câu), citations[], confidence, escalate, refused, reason, answer_mode,
  procedure}`. Trích dẫn có thêm `agency`, `source_portal`, `fetched_at`, `effective_date`,
  `section`, `procedure_id`. `reason`: `ok | no_source | sensitive | real_action | pasted_content |
  verify_failed | kb_not_ready`; `answer_mode`: `llm_verified | template | safety | no_source`
  (chế độ `llm_unverified` chỉ dùng cho đánh giá, API không bao giờ trả — nếu gặp thì 500).
  `procedure` là thẻ thủ tục `{procedure_id, ten, co_quan, source_url, fetched_at, documents[],
  fees[], cases[]}` hoặc `null`. **Không bao giờ** trả `diagnostics` của bộ máy trả lời.
- Lỗi: 401/403 (chỉ vai người dân), 422, `503 KB_NOT_READY` khi chưa có chỉ mục,
  `500 ANSWER_FAILED` khi bộ máy lỗi bất ngờ.
- Quyền riêng tư: API không ghi log và không lưu câu hỏi; lỗi bất ngờ chỉ ghi tên loại lỗi
  (thông điệp lỗi có thể chứa câu hỏi). Có test bất biến `tests/invariants/test_api_ask_privacy.py`.

### Kiểm hồ sơ cho cán bộ (`POST /v1/coach/intake-check`, ADR-007 C6)

- Vai TNV hoặc cán bộ; không dùng LLM, không phải tool của agent.
- Vào: `IntakeCheckIn{procedure_id? | query? (2..200), received: [d01…] (≤ 60, không trùng),
  case_label? (≤ 2000, bằng `MAX_CASE_LABEL` của agent — nhãn thật dài tới 918 ký tự)}` — phải có **đúng một** trong `procedure_id` và `query`.
- Ra: `IntakeCheckOut{procedure, alternatives (≤ 3), cases, needs_case, items[{…, status:
  da_nhan | thieu | neu_ap_dung}], missing_count, message_for_citizen (≤ 2 câu), citations}` —
  `neu_ap_dung` (v2): giấy tờ mà tên tự nêu trường hợp riêng, chưa nhận; không tính vào `missing_count`.
- Lỗi: `404 PROCEDURE_NOT_FOUND`, 422, `503 KB_NOT_READY`, `500 INTAKE_FAILED`.

### Nối dịch vụ (`ctcv_api.knowledge`)

Lần gọi đầu tiên cần tới kho thủ tục sẽ nạp chỉ mục file (`FileKnowledgeBase` + `OllamaEmbedder`),
dựng `AnswerEngine` (`build_engine`) và `IntakeChecker` trên **cùng một** kho, gọi
`wire_default_backends` một lần rồi giữ hai dịch vụ trên `app.state` (có khóa `threading.Lock`).
Lỗi khi dựng (`KB_NOT_READY`) không được ghi nhớ: yêu cầu sau sẽ dựng lại khi chỉ mục đã có. Dịch vụ đặt sẵn
trên `app.state.answer_service` / `app.state.intake_service` (test) được dùng nguyên.
Xây chỉ mục: `uv run python -m ctcv_data.pipeline chunk_embed --online` (xem `services/agent`).

### Chế độ demo (ADR-007 C6, C10)

Mặc định **tắt**: `join` và `login` trả 501 như E01. Bật cho buổi demo cục bộ bằng biến môi trường
tạm thời (script `scripts/dev_cpu.py` tự sinh, không ghi vào repo, không in ra):

```bash
export CTCV_DEMO_QR_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
export CTCV_DEMO_STAFF_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(18))')"
uv run ctcv-api
```

- `POST /v1/auth/join` với đúng `qr_token` → JWT vai người dân, `user_id =
  demo-citizen-<8 ký tự đầu sha256(display_name)>` (không giữ biệt danh); sai mã → 501.
- `POST /v1/auth/login` với `username = config/rag.yaml: demo.staff_username` và đúng mật khẩu →
  JWT vai cán bộ, `user_id = demo-officer`; sai → `401 INVALID_CREDENTIALS`
  ("Tên đăng nhập hoặc mật khẩu chưa đúng, anh/chị kiểm tra lại nhé.").
- So sánh bằng `hmac.compare_digest` (hằng thời gian); bí mật là `SecretStr`, không vào log, lỗi
  cấu hình không in lại giá trị (`hide_input_in_errors`). Biến để trống = tắt.
- `CTCV_ENV=prod` mà đặt một trong hai biến → API **từ chối khởi động**. v2: `CTCV_ENV` được chuẩn hóa
  (bỏ khoảng trắng, không phân biệt hoa thường; `production` = `prod`); bật demo mà `JWT_SECRET` còn là
  giá trị mặc định/`CHANGE_ME` → cũng từ chối khởi động (khóa mặc định công khai trong mã).

## Định dạng lỗi thống nhất

Mọi lỗi (kể cả 401/403/404/422/429/500) đều có dạng:

```json
{"error": {"code": "SCENARIO_NOT_FOUND", "message": "Không tìm thấy bài học này, bác thử chọn bài khác nhé."}}
```

`code` là mã ổn định (UPPER_SNAKE), `message` là câu tiếng Việt an toàn để hiển thị cho người dân;
`details` (tùy chọn) là ngữ cảnh máy đọc, không bao giờ chứa PII. Nguồn: `ctcv_core.errors.AppError`
và các lớp con; trong API thêm `UnauthorizedError` (401), `InvalidCredentialsError` (401),
`AnswerFailedError`/`IntakeFailedError` (500) ở `ctcv_api.errors`; `KB_NOT_READY` (503) và
`PROCEDURE_NOT_FOUND` (404) đến từ `ctcv_agent.rag.types`; các `HTTPException`
của Starlette (404, 405, 413, 429…) được `ctcv_api.handlers` đổi sang cùng định dạng.
Mã 501 dùng `code: NOT_IMPLEMENTED`, `details.epic` cho biết epic sẽ hiện thực.

Mỗi phản hồi có header `X-Request-ID` (nhận từ client hoặc tự sinh); giá trị này đi vào mọi dòng
log JSON (`ctcv_core.logging`).

## Xác thực và phân quyền

- `ctcv_api.auth.create_token(user_id, role, settings)` — JWT HS256, hạn `JWT_TTL_MINUTES`.
- `current_user` — dependency đọc `Authorization: Bearer`, trả `Principal{user_id, role}`.
- `require_role("volunteer", "officer")` — dependency chặn vai khác bằng 403 `FORBIDDEN`.
- Ba vai lấy từ `config/app.yaml: roles` (citizen, volunteer, officer).

## Cơ sở dữ liệu và migration

9 bảng (brief §4) trong `ctcv_api/models.py`: `users`, `classes`, `scenarios`, `sessions`, `events`,
`qa_logs`, `drills`, `screen_jobs`, `audit`. Kiểu cột generic (`Uuid`, `JSON`, `DateTime(timezone=True)`,
`Enum(native_enum=False)`) nên SQLite chạy được trong test (D15) và PostgreSQL ở production.

Bất biến về quyền riêng tư (có test):

- không cột CCCD / điện thoại / e-mail / mật khẩu / OTP trong bất kỳ bảng nào;
- `users.display_name` là **biệt danh hoặc mã do tình nguyện viên cấp** (≤ 32 ký tự, không phải họ tên thật);
- `classes.qr_token` có `qr_token_expires_at` và `qr_token_revoked_at` (D27);
- `events.payload_json` chỉ nhận các khóa trong allowlist theo `type` (`ctcv_api.events_schema.validate_payload`,
  D28) — khóa văn bản tự do bị từ chối trước khi ghi;
- `qa_logs` chỉ lưu băm câu hỏi/câu trả lời.

Migration Alembic nằm ở `services/api/alembic/` (`alembic.ini` cùng thư mục), đọc `DATABASE_URL`
từ `Settings`:

```bash
cd services/api
uv run alembic upgrade head                 # áp dụng
uv run alembic downgrade base               # quay lui
uv run alembic revision --autogenerate -m "mo_ta"   # sau khi đổi models.py — đọc lại file sinh ra rồi mới commit
```

Migration đã merge vào `main` không được sửa (hook protect-paths); tạo migration mới thay vì sửa.
Đổi schema sau E05 là điểm dừng bắt buộc (hỏi người dùng, ghi ADR — plan §6).

## Thêm một endpoint mới

1. Cập nhật hợp đồng trong `docs/plan.md` §5 (và brief §3 nếu đổi request/response) **trước**;
   ghi ADR nếu đổi schema DB, tool hay model.
2. Thêm model request/response vào `ctcv_api/schemas.py` (mô tả trường bằng tiếng Việt).
3. Viết contract test trong `services/api/tests/` trước (mã trạng thái, schema, quyền).
4. Thêm hàm xử lý vào router tương ứng trong `ctcv_api/routers/`; dùng `Annotated[..., Depends(...)]`,
   `require_role(...)` nếu cần; lỗi → raise lớp con của `AppError`, không trả dict lỗi thủ công.
5. Cập nhật bảng endpoint trong README này và `CHANGELOG.md`.

## Kiểm thử

```bash
uv run pytest services/api -q --cov=ctcv_api --cov-report=term-missing
uv run ruff check services/api && uv run ruff format services/api
```
