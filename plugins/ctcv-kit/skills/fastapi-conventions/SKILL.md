---
name: fastapi-conventions
description: Quy ước FastAPI, Pydantic v2, SQLAlchemy 2, Alembic và contract API /v1 của CTCV (services/api, services/agent). Use when implementing or testing any HTTP endpoint, DB model, migration or agent tool.
---
# Quy ước backend CTCV (FastAPI + SQLAlchemy 2 + Alembic)

## Contract API (brief §3 — ràng buộc, 16 route, prefix `/v1`, JSON, JWT Bearer)
| Route | Vai | Model | E01 |
| --- | --- | --- | --- |
| `POST /v1/auth/join` · `POST /v1/auth/login` | citizen · volunteer/officer | `JoinRequest{qr_token, display_name, accent_pref?}` / `LoginRequest` → `TokenResponse{token, user_id, role}` | stub 501 |
| `POST /v1/classes` · `GET /v1/classes/{id}/progress` · `GET /v1/reports/class/{id}?format=pdf\|xlsx` | volunteer/officer | `ClassCreate` → `ClassOut{class_id, qr_url, qr_token}`; `ClassProgress{rows[], needs_coaching[]}` | stub 501 |
| `GET /v1/scenarios?skill=&level=` | all | `list[ScenarioSummary]` đọc `sandbox/scenarios/*.json` | **thật** |
| `POST /v1/sessions` · `POST /v1/sessions/{id}/events` (SSE `{state, say}`) | citizen | `SessionCreate{scenario_id}` → `SessionOut`; `SessionEvent{type: tap\|input\|ask\|back, target?, value?}` | stub 501 |
| `POST /v1/speech/asr` · `POST /v1/speech/tts` | all | multipart → `AsrOut{text, confidence, accent_tag}`; `TtsIn{text}` → `TtsOut{audio_url, cached}` | stub 501 |
| `POST /v1/coach/ask` · `POST /v1/coach/screen` | citizen | `AskIn{question, session_id?}` → `AskOut{answer, citations[], confidence, escalate}`; ảnh → `ScreenOut{screen_state, step_text, boxes[]}` | stub 501 |
| `POST /v1/drills` · `POST /v1/drills/{id}/answers` | citizen | `DrillStart{scenario_key?}` → `DrillOut`; `DrillAnswer{option_id}` → `DrillResult{score, red_flags[], debrief, three_things[]}` | stub 501 |
| `GET /v1/health`, `/health` · `GET /v1/metrics`, `/metrics` | system | `{status, version, checks{db, redis, qdrant}}` ("skipped" khi chưa cấu hình); Prometheus text | **thật** |

- Tên model: `XxxRequest`/`XxxIn` cho vào, `XxxOut`/`XxxResponse` cho ra; Pydantic v2 (`model_config = ConfigDict(extra="forbid")` cho đầu vào).
- Lỗi: raise `ctcv_core.errors.AppError` (hoặc `NotFound`, `Forbidden`, `ValidationFailed`, `NotImplementedYet`); exception handler chung trả `{"error": {"code", "message"}}` với message tiếng Việt đời thường. Không lộ stack trace.
- `user_id`/`role` lấy từ JWT (dependency), **không** nhận từ body/query/tham số tool (D28). JWT ngắn hạn (`jwt_ttl_minutes` trong `config/app.yaml`), `JWT_SECRET` từ env.
- Rate limit theo `rate_limit_per_min`; `max_concurrent_sessions`; mọi giá trị đọc qua `ctcv_core.load_config("app")`.
- **Không endpoint liệt kê drills** (server chọn biến thể — D27); `qr_token` có `expires_at`, `revoked_at`.
- Mọi route có **test hợp đồng** (schema request/response, mã lỗi) ngay từ E01, kể cả stub 501.

## DB (brief §4)
- SQLAlchemy 2 declarative, bảng số nhiều, `id: Uuid` (kiểu generic để chạy SQLite in-memory — D15), thời gian UTC `DateTime(timezone=True)`, `JSON` generic; enum: `role` citizen/volunteer/officer, `accent_pref` bac/trung/nam/null.
- 9 bảng: users, classes, scenarios, sessions, events, qa_logs, drills, screen_jobs, audit. **Không** cột CCCD/điện thoại/email bắt buộc/OTP/mật khẩu người dân; `qa_logs` chỉ lưu hash câu hỏi/đáp; `events.payload_json` allowlist theo `type` (input ⇒ `{field_id, valid, len}`; ask ⇒ `{intent_class, hmac}`); `screen_jobs` chỉ lưu `boxes_json`, ảnh ở MinIO TTL 60 s.
- Alembic: `services/api/alembic/versions/0001_init` …; migration đã có trên `main` là bất biến (hook chặn) — tạo migration mới có test di trú; đổi schema sau E05 là điểm dừng bắt buộc.
- Test unit: SQLite in-memory qua fixture chung; integration (PostgreSQL testcontainers) đánh dấu `@pytest.mark.integration`.

## Agent service (brief §7)
- Tool: một module mỗi tool trong `ctcv_agent/tools/`, `Input`/`Output` Pydantic, `run(inp) -> Output`, `SIDE_EFFECT: Literal["none","sandbox","log"]`; `TOOL_REGISTRY` là `MappingProxyType`; router chỉ gọi tool có trong registry **và** `config/tools.yaml`; tên lạ → `ToolNotAllowed`. Module tool không import `httpx`/`requests`/`subprocess`.
- `PlannerOutput{say ≤ 2 câu, action_hint{element_id, color, label}|null, tool_calls[], confidence 0..1}`; guardrails `redact_pii`, `refuses_sensitive_request`, `refuses_real_action`, `enforce_style`, `requires_citation` với regex/ngưỡng từ `config/guardrails.yaml`.
- Quarantine trả **schema kín** (enum intent, mã red_flag, số tiền, danh mục cơ quan; không text tự do); VLM trả `screen_id` thuộc catalog + `element_id`. Không chuỗi untrusted đi thẳng vào prompt planner (taint test).
- Escalate khi `confidence < escalate_confidence` (0,6 mặc định, câu hỏi mở E05).

## Checklist trước khi báo xong
`uv run pytest services/api` (hoặc `services/agent`) xanh · contract test đủ route · `make check QUICK=1` xanh · README mô-đun + CHANGELOG · không secret, không PII trong fixture/log · không thư viện ngoài `config/allowed-deps.yaml`.
