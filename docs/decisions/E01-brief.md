# E01 — Bản thiết kế bootstrap (architect brief) — v2

Ngày: 2026-09-18 (v1 sáng, v2 sau rà soát 6 lăng kính — xem `docs/analysis/2026-09-18-review-findings.md`) · Trạng thái: quyết định cho E01, mọi thay đổi sau này qua ADR. Nguồn sự thật: `docs/idea.md` (sản phẩm) > `docs/plan.md` (quy trình, kiến trúc) > `docs/prompt.md` (vận hành Claude Code) > `docs/competition/BTC-2026-yeu-cau.md` (yêu cầu BTC đã xác minh, thắng tất cả về hồ sơ). Quy tắc ưu tiên: brief v2 thắng ba file gốc **chỉ ở những điểm nó liệt kê rõ trong §0 và §17**; ngoài ra ba file thắng. Brief này chốt các điểm mà ba file để mở hoặc mâu thuẫn, để nhiều agent dựng khung song song mà vẫn nhất quán.

## 0. Quyết định chốt (deviation có lý do — ghi vào ADR-001/002)

| # | Quyết định | Lý do |
| --- | --- | --- |
| D1 | Repo root = `D:\AiSangTao2026` (tên GitHub `ctcv`), nhánh `main`. Ba file nguồn sự thật nằm ở `docs/idea.md`, `docs/plan.md`, `docs/prompt.md` | plan §4 mục 10 |
| D2 | Hook Claude Code viết bằng **Python 3** (gọi qua `bash .claude/hooks/run.sh <tên>`), không dùng jq | Máy dev là Windows (Git Bash); jq không có sẵn; cùng một mã chạy trên Linux CI/server |
| D3 | Bỏ hai biến `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` khỏi settings (không tồn tại trong binary); giữ `CLAUDE_CODE_SUBAGENT_MODEL=fable`. Giới hạn 6 subagent đồng thời / 2 tầng ghi trong CLAUDE.md (luật cho orchestrator) | Đã xác minh trên CLI 2.1.119 |
| D4 | Stop hook kiểu `agent` trong prompt.md 9.1 thay bằng hook Python **không chặn**: nhắc "make check chưa xanh sau thay đổi mã" qua stderr; cổng cứng nằm ở `/epic` (skill) và CI | Hook chặn Stop có thể khóa phiên khi làm việc ad-hoc; cổng chất lượng thật là CI + PR |
| D5 | Thư viện dùng chung `libs/core` (package `ctcv_core`): nạp config có kiểm schema, lỗi có mã + thông điệp tiếng Việt, log JSON không PII | Ba file không nói mã dùng chung để đâu; tránh copy giữa 6 dịch vụ |
| D6 | `drills/` là thư mục gốc (package `ctcv_drills`) theo plan §7/§15; idea 15.1 không có → plan thắng | Quy trình |
| D7 | Bộ phát hiện giao diện = **YOLOX-Tiny (Apache-2.0)**, không dùng Ultralytics YOLO (AGPL-3.0, không tương thích Apache-2.0 của repo) | Giấy phép; plan đã ghi YOLOX |
| D8 | Model APK offline = **Qwen3.5-2B** (Qwen3.5 không có bản 1.7B; dải nhỏ là 0.8B/2B/4B/9B) — ghi trong `config/models.yaml` là `planner_small` | Đã xác minh trên Hugging Face |
| D9 (v2) | **Một model phục vụ**: `vlm` trong `config/models.yaml` trỏ cùng `Qwen/Qwen3.5-9B` (đa phương thức native) — planner dùng LoRA adapter cho lượt huấn luyện viên, lượt đọc ảnh dùng base (multi-LoRA của vLLM). `Qwen3-VL-8B` chỉ còn là phương án B trong ADR-002. Lý do: hai instance vLLM + KV cache 50 người không vừa 24 GB, vLLM không hot-swap model. **Trạng thái: đề xuất, người dùng chốt tại PR E01** (đổi model là điểm dừng bắt buộc); spike 2 giờ trên máy GPU (AWQ + LoRA + vision cùng lúc) là điều kiện chốt; nếu vLLM chưa hỗ trợ → Qwen3.5-4B bf16 làm cả hai | F03, C03 gap |
| D10 | Giấy phép PhoWhisper = **BSD-3-Clause** (idea 15.4 ghi Apache-2.0 là sai) — sửa trong registry | Đã xác minh |
| D11 | Cấu trúc PDF hồ sơ theo **13 mục MẪU 3 của BTC** (không phải dàn ý 10 khối của idea §12); `docs/dossier/src/00..13` | BTC bắt buộc |
| D12 | Prompt log: transcript `.jsonl` + `INDEX.md` có SHA-256 trong `docs/prompt-log/` (commit vào repo) **và** đồng bộ lên thư mục Google Drive công khai (mục 13 của mẫu) | BTC yêu cầu link Drive |
| D13 (v2) | Hai cổng: `make check` = **tất định, không cần model** (lint, unit, integration, contract API, schema config, bất biến, red-team qua guardrail thuần, audit, docs-check; thêm e2e Playwright và docker build khi `QUICK≠1`) chạy mỗi PR trên GitHub-hosted; `make gate` = **cần GPU/staging** (eval --quick với LLM-judge, red-team có model, loadtest) chạy hằng đêm trên self-hosted runner ở máy GPU và trước mỗi tag. CI không bao giờ gọi model | F10, S9, C04 gap |
| D14 | Dockerfile của mọi dịch vụ nằm ở `deploy/docker/<svc>.Dockerfile`, context = repo root | Tách quyền sở hữu thư mục khi nhiều agent làm song song |
| D15 | Kiểm thử unit chạy trên SQLite in-memory (kiểu cột generic: `Uuid`, `JSON`); tích hợp với PostgreSQL bằng testcontainers từ E02 | Máy dev không cần Postgres để chạy unit |
| D16 | Tiếng Anh cho mã, docstring, commit; tiếng Việt cho UI, thông điệp lỗi người dùng, tài liệu, epic, ADR | plan §3 |
| D17 (v2) | Subagent dùng `model: inherit` (kế thừa `"model": "claude-fable-5-1"` của settings.json); **không** dùng alias `fable` (CLI 2.1.119 không có); không đặt `CLAUDE_CODE_SUBAGENT_MODEL`; thêm `"effortLevel": "xhigh"` vào settings | CC-03, CC-05 |
| D18 (v2) | `qa-tester` **không** `background: true` (là cổng đồng bộ trước reviewer). `isolation: worktree` giữ cho backend-dev/frontend-dev nhưng chỉ có tác dụng sau commit đầu tiên; E01 không dùng worktree; CLAUDE.md ghi rõ | CC-10, CC-11 |
| D19 (v2) | `architect` read-only (`permissionMode: plan`), trả nội dung ADR trong tóm tắt; `docs-writer` hoặc orchestrator ghi file ADR. `reviewer` chỉ Read/Grep/Glob (bỏ Bash); `security-redteam` có Bash + Write/Edit nhưng protect-paths chỉ cho ghi `eval/redteam/**`, `docs/security/**` | CC-09 |
| D20 (v2) | Prompt log: `docs/prompt-log/sessions/<session_id>.jsonl` (Stop = ghi đè idempotent, **không** đụng INDEX; SessionEnd = chép lần cuối + sha256 + 1 dòng INDEX + snapshot hash "system prompt" (CLAUDE.md, .claude/agents, .claude/skills, settings.json, config/prompts) vào `docs/prompt-log/system/<session_id>.json`); `SubagentStop` chép `agent_transcript_path` (nếu có) vào `docs/prompt-log/subagents/`; `make promptlog-sync` nhập mọi transcript từ `~/.claude/projects/<slug>/` chưa có trong INDEX; `docs/prompt-log/tools/` lưu prompt template của bước sinh dữ liệu/LLM-judge; `docs/prompt-log/pre-D1/` cho hội thoại đã soạn 3 tài liệu (người dùng xuất tay). docs-check chỉ kiểm INDEX hợp lệ và hash khớp, không đòi "phiên hiện tại đã có log" | C07, CC-02, CF-03, CF-04, N12, N14 |
| D21 (v2) | Trước khi lên Drive/ZIP: `make promptlog-export` chạy gitleaks + regex PII trên log; phát hiện → **redaction tự động** thay bằng `[REDACTED-SECRET sha256:<8>]`, ghi lại trong INDEX và README (không phải "làm giả", là chính sách công bố). Dữ liệu pilot thô không bao giờ lên Drive/repo | SEC-01 |
| D22 (v2) | Hook fail-closed cho guard/protect-paths (lỗi parse → exit 2). guard chặn thêm: `git commit --no-verify`, `git -c core.hooksPath`, `git config core.hooksPath`, `docker compose config` (không `--no-interpolate`), `printenv`, lệnh `env`/`set` đứng một mình, mọi token khớp `(^|[\s/"'=])\.env(\.[\w-]+)?\b`, `rm` với cờ r+f mọi thứ tự; trigger ngân sách chỉ khi `^(make (train|data|finetune)\b|uv run (python )?-m ctcv_training|uv run python training/)`. protect-paths matcher `Edit\|MultiEdit\|Write\|NotebookEdit`; bảo vệ thêm `.claude/**`, `CLAUDE.md`, `.github/workflows/**`, `.pre-commit-config.yaml`, `Makefile` **trừ khi** tồn tại marker `.claude/BOOTSTRAP` (có trong E01, xóa khi merge E01); migration chặn khi `git cat-file -e main:<path>` thành công; `config/eval.yaml` sửa được khi `CTCV_ALLOW_EVAL_THRESHOLD=1` hoặc file chưa có trên main | CC-07, CC-08, SEC-02, N11 |
| D23 (v2) | PostToolUse `format` chỉ `ruff format` + prettier (không `--fix`, không pytest); test chạy ở `make check`/pre-commit | N13 |
| D24 (v2) | `.mcp.json` chỉ có `playwright` (trên Windows gọi qua `cmd /c npx …`; Linux thêm ở user scope); GitHub qua `gh` CLI (cài `winget install GitHub.cli`) với allow `Bash(gh *)`; settings có `enableAllProjectMcpServers: false`, `enabledMcpjsonServers: ["playwright"]`. Xóa file `mcp.json` rỗng | CC-12 |
| D25 (v2) | Thông tin cá nhân thành viên đội **không** vào repo: `docs/dossier/private/team.yaml` (gitignore) + `team.example.yaml`; build_dossier đọc từ private; gitleaks rule tùy chỉnh cho SĐT/email VN trong `docs/**` | N09 |
| D26 (v2) | `config/allowed-deps.yaml` là allow-list thư viện duy nhất (tên, giấy phép, lý do, epic); `make audit` kiểm lockfile ⊆ danh sách và không có AGPL/GPL/CC-NC trong runtime; CLAUDE.md chỉ tham chiếu file này. Cấm `ultralytics`, `yolov5` | N07, LIC-07 |
| D27 (v2) | Drills: thêm trường `utterance` (đúng 1 lượt, ≤ 40 từ, bắt buộc có "[Mô phỏng]" khi TTS/SMS; cấm URL, SĐT, STK, tên ngân hàng/cơ quan thật, chuỗi leo thang nhiều lượt); `/drills` chọn biến thể phía server, không endpoint liệt kê; `qr_token` có hạn và thu hồi được | SEC-06 |
| D28 (v2) | Quarantine trả **schema kín** (enum intent, mã red_flag, số tiền, danh mục cơ quan; không trường text tự do); VLM trả `screen_id` thuộc catalog + `element_id`; `user_id` lấy từ JWT, bỏ khỏi tham số tool; `events.payload_json` có allowlist trường theo `type` (input ⇒ {field_id, valid, len}; ask ⇒ {intent_class, hmac}); `display_name` là biệt danh/mã do TNV cấp; ADR-005 có bảng retention (events/sessions/qa_logs/drills 90 ngày, log app 30 ngày, backup 14 bản) | SEC-03, SEC-04 |
| D29 (v2) | Compose profiles `cpu` (máy dev Windows, CI) và `gpu` (máy thuê); dev trỏ `VLLM_BASE_URL` sang máy GPU (SSH tunnel/Tailscale) hoặc `llama.cpp` server với `Qwen3.5-2B/4B` GGUF làm đường CPU chính thức (dev, demo dự phòng, hackathon, fallback chung kết) — `planner_small` trong `models.yaml` phục vụ mục này chứ không phải APK. `make doctor` = doctor-dev; `make doctor GPU=1` kiểm tra máy GPU qua SSH. docx→pdf bằng container LibreOffice | F11, S7, C02 gap |
| D30 (v2) | Lịch thật 3 pha (đề xuất, chờ người dùng chốt — ADR-006): Pha A 18/9–29/9 hồ sơ sơ bộ (tuyến trường 30/9; E01→E02 4 kịch bản→E03-lite→E04→E05 base+guardrail→E09-lite 10 drill→E10-lite dashboard→staging HTTPS+status→thử nghiệm sơ bộ n=5–10 (26–27/9)→2 video→dossier 13 mục); Pha B 1/10–9/10 kit hackathon + 2 diễn tập; Pha C 12–18/10 cổng quyết định; Pha D 19/10–17/11 E06–E08, E10 đủ, E11 đủ, E12 prod+dự phòng, pilot 30 người (27/10–9/11), hồ sơ cập nhật; freeze 17–19/11. APK offline → PWA offline (đề xuất cắt); "kèm cặp trên app thật" → hướng phát triển, bản nộp chỉ kèm cặp trên ảnh sandbox (đề xuất) | CF-01, S1–S6, F09, N06, C01/C05 gap |
| D31 (v2) | Không tự sửa cấu trúc/lịch trong `docs/idea.md`, `docs/plan.md`, `docs/prompt.md` (quyết định của người dùng); chỉ ghi **errata sự kiện** vào cuối mỗi file (Qwen3.5-1.7B→2B, PhoWhisper BSD-3-Clause, YOLO→YOLOX-Tiny, `mcp.json`→`.mcp.json`, hạn nộp) kèm ngày; mọi đề xuất cấu trúc nằm ở ADR-006 và `docs/analysis/` | quy trình thay đổi plan §11 |

## 1. Cây thư mục chuẩn (bắt buộc — không tạo thư mục ngoài danh sách khi chưa hỏi)

```
ctcv/
  CLAUDE.md  README.md  LICENSE  SECURITY.md  CHANGELOG.md  Makefile
  .env.example  .gitignore  .gitattributes  .editorconfig  .dockerignore  .python-version
  pyproject.toml  uv.lock  pnpm-workspace.yaml  package.json  .pre-commit-config.yaml  .mcp.json
  .claude/            settings.json  agents/*.md  skills/*/SKILL.md  hooks/run.sh + *.py
  .github/            workflows/check.yml  workflows/nightly-eval.yml  workflows/release.yml  PULL_REQUEST_TEMPLATE.md
  plugins/ctcv-kit/   .claude-plugin/plugin.json  agents/  skills/  hooks/hooks.json  .mcp.json  (sinh bởi `make plugin`)
  epics/              E01.md … E12.md  PILOT.md  DOSSIER.md
  config/             app.yaml  models.yaml  tools.yaml  guardrails.yaml  eval.yaml  prompts/*.v1.md  schemas/*.schema.json
  libs/core/          pyproject.toml  src/ctcv_core/  tests/
  apps/web/           Vite + React 18 + TS + Tailwind PWA (src/, tests/, e2e/, public/)
  apps/android/       README.md (E12)
  services/api/       pyproject.toml  src/ctcv_api/  alembic/  tests/
  services/agent/     pyproject.toml  src/ctcv_agent/  tests/
  services/speech/    pyproject.toml  src/ctcv_speech/  tests/
  services/vision/    pyproject.toml  src/ctcv_vision/  tests/
  sandbox/            pyproject.toml  src/ctcv_sandbox/  scenarios/*.json  tests/
  drills/             pyproject.toml  src/ctcv_drills/  scenarios/*.json  tests/
  data/               pyproject.toml  src/ctcv_data/pipeline/  sources.yaml  registry/{datasets,models}.yaml  raw/ clean/ ui/ sft/ dpo/ (gitignore)
  training/           pyproject.toml  src/ctcv_training/  configs/*.yaml  budget.json  runs/ (gitignore)  reports/
  eval/               pyproject.toml  src/ctcv_eval/  redteam/scenarios.jsonl  loadtest/k6.js  sets/ (gitignore lớn)  pilot/  reports/
  deploy/             docker-compose.yml  docker-compose.dev.yml  docker-compose.prod.yml  docker/*.Dockerfile  caddy/Caddyfile  monitoring/  models/  scripts/*.sh  status/
  scripts/            doctor.py  check_docs.py  promptlog_export.py  declaration.py  gen_schemas.py  sync_plugin.py
  tests/              conftest.py  invariants/  config/
  hackathon/          README.md  input/.gitkeep
  docs/               idea.md  plan.md  prompt.md  competition/  decisions/  status/  prompt-log/  dossier/{src,build,out}  template/  ops/  screens/  pilot/  analysis/
```

## 2. Stack và phiên bản (khớp CLAUDE.md)

Python 3.12 (uv workspace, một `uv.lock` ở gốc), FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx, PyYAML, jsonschema, pytest + pytest-cov, ruff (lint + format). Node 20+ (máy dev có 24), pnpm workspace, React 18, Vite 5, TypeScript strict, Tailwind 3, vitest, Playwright, eslint + prettier. PostgreSQL 16, Redis 7, Qdrant 1.x, MinIO, vLLM (OpenAI-compatible), faster-whisper, YOLOX + onnxruntime, Caddy 2, Uptime Kuma, Prometheus, Grafana. Docker Compose v2. Thư viện ngoài danh sách này → hỏi trước, ghi ADR.

Tên gói Python (distribution → import): `ctcv-core → ctcv_core`, `ctcv-api → ctcv_api`, `ctcv-agent → ctcv_agent`, `ctcv-speech → ctcv_speech`, `ctcv-vision → ctcv_vision`, `ctcv-sandbox → ctcv_sandbox`, `ctcv-drills → ctcv_drills`, `ctcv-data → ctcv_data`, `ctcv-training → ctcv_training`, `ctcv-eval → ctcv_eval`. Mọi gói dùng `src/` layout, `[build-system] hatchling`. Phụ thuộc nội bộ khai báo qua `[tool.uv.sources] ctcv-core = { workspace = true }`.

Cổng mặc định (config/app.yaml): api 8000, agent 8010, speech 8020, vision 8030, models (vLLM) 8040, web dev 5173, caddy 80/443, postgres 5432, redis 6379, qdrant 6333, minio 9000/9001, uptime-kuma 3001, prometheus 9090, grafana 3000.

## 3. Hợp đồng API (`services/api`, prefix `/v1`, JSON, JWT Bearer)

| Method | Path | Vai | Request → Response (Pydantic) | E01 |
| --- | --- | --- | --- | --- |
| POST | `/v1/auth/join` | citizen | `JoinRequest{qr_token, display_name, accent_pref?}` → `TokenResponse{token, user_id, role}` | stub 501 |
| POST | `/v1/auth/login` | volunteer/officer | `LoginRequest{username, password}` → `TokenResponse` | stub 501 |
| POST | `/v1/classes` | volunteer | `ClassCreate{name, ward_code}` → `ClassOut{class_id, qr_url, qr_token}` | stub 501 |
| GET | `/v1/classes/{class_id}/progress` | volunteer/officer | → `ClassProgress{rows[], needs_coaching[]}` | stub 501 |
| GET | `/v1/reports/class/{class_id}?format=pdf\|xlsx` | volunteer/officer | file | stub 501 |
| GET | `/v1/scenarios?skill=&level=` | all | → `list[ScenarioSummary]` đọc từ `sandbox/scenarios/*.json` | **thật** |
| POST | `/v1/sessions` | citizen | `SessionCreate{scenario_id}` → `SessionOut{session_id, screen}` | stub 501 |
| POST | `/v1/sessions/{session_id}/events` | citizen | `SessionEvent{type: tap\|input\|ask\|back, target?, value?}` → SSE stream `{state, say}` | stub 501 |
| POST | `/v1/speech/asr` | all | multipart audio → `AsrOut{text, confidence, accent_tag}` | stub 501 |
| POST | `/v1/speech/tts` | all | `TtsIn{text}` → `TtsOut{audio_url, cached}` | stub 501 |
| POST | `/v1/coach/ask` | citizen | `AskIn{question, session_id?}` → `AskOut{answer, citations[], confidence, escalate}` | stub 501 |
| POST | `/v1/coach/screen` | citizen/volunteer | multipart image → `ScreenOut{screen_state, step_text, boxes[]}` | stub 501 |
| POST | `/v1/drills` | citizen | `DrillStart{scenario_key?}` → `DrillOut{drill_id, scenario}` | stub 501 |
| POST | `/v1/drills/{drill_id}/answers` | citizen | `DrillAnswer{option_id}` → `DrillResult{score, red_flags[], debrief, three_things[]}` | stub 501 |
| GET | `/v1/health`, `/health` | system | `{status, version, checks{db, redis, qdrant}}` | **thật** (checks "skipped" nếu chưa cấu hình) |
| GET | `/v1/metrics`, `/metrics` | system | Prometheus text | **thật** (counter tối thiểu) |

Lỗi thống nhất: HTTP status + `{"error": {"code": "SCENARIO_NOT_FOUND", "message": "Không tìm thấy bài học này, bác thử chọn bài khác nhé."}}`. Stub 501 trả `code: NOT_IMPLEMENTED` và message tiếng Việt. Mọi endpoint có test hợp đồng (schema request/response) ngay từ E01.

## 4. Schema PostgreSQL (SQLAlchemy 2, bảng số nhiều, id UUID, thời gian UTC, Alembic `0001_init`)

| Bảng | Cột | Ràng buộc |
| --- | --- | --- |
| users | id, role (enum citizen/volunteer/officer), display_name, class_id FK→classes nullable, accent_pref (enum bac/trung/nam/null), consent_at, created_at | KHÔNG có cột CCCD/điện thoại/email bắt buộc |
| classes | id, name, ward_code, volunteer_id FK→users, qr_token unique, created_at | ward_code theo danh mục hành chính 2026 |
| scenarios | id (text, = id trong JSON), skill_group, level, spec_json (JSON), version, checksum | nạp từ `sandbox/scenarios/*.json` |
| sessions | id, user_id, scenario_id, started_at, ended_at, success bool, steps int, mistakes int, hints_used int, duration_s int | |
| events | id, session_id, ts, type (tap/input/hint/error/ask), payload_json | payload không chứa PII (kiểm bằng regex ở tầng ghi) |
| qa_logs | id, user_id, question_hash, answer_hash, citations_json, confidence, escalated, ts | không lưu nguyên văn |
| drills | id, user_id, scenario_key, attempt, score, red_flags_json, ts | |
| screen_jobs | id, user_id, created_at, deleted_at, boxes_json | ảnh chỉ ở MinIO TTL 60 s |
| audit | id, actor_id, action, target, ts | |

## 5. Schema kịch bản sandbox (`ctcv_sandbox.schema`, JSON Schema xuất ra `config/schemas/scenario.schema.json`)

```json
{
  "id": "chuyen-khoan-qr",            // slug [a-z0-9-], duy nhất
  "skill_group": "thanh-toan-thue-so", // enum: thiet-bi-co-ban | dinh-danh-vneid | dich-vu-cong | thanh-toan-thue-so | an-toan-so
  "level": 1,                          // 1..3
  "version": "1.0.0",
  "app_label": "Ứng dụng mô phỏng ngân hàng",   // nhãn "Ứng dụng mô phỏng" bắt buộc có trong chuỗi
  "goal": "Chuyển 200.000đ cho con bằng quét mã QR",
  "intent_confirmation": "Bác muốn chuyển tiền cho con hay trả tiền hàng?",
  "start_screen": "home",
  "screens": [{
    "id": "home",
    "title": "Trang chính",
    "elements": [{"id": "btn_qr", "kind": "button|input|text|banner", "label": "Quét QR", "color": "xanh|do|vang|xam|trang", "sensitive": false}],
    "valid_actions": [{"tap": "btn_qr", "next": "scan"}],           // hoặc {"input": "amount", "value_pattern": "^\\d+$", "next": "confirm"}
    "common_mistakes": [{"tap": "btn_promo", "hint": "Đó là quảng cáo, bác bấm nút xanh có chữ Quét QR nhé"}],
    "coach_line": "Bác bấm nút xanh có chữ Quét QR nhé.",            // ≤ 2 câu
    "terminal": false
  }],
  "success": {"screen": "done", "conditions": {"amount": 200000}},
  "never_ask": ["otp", "mat_khau", "so_the"],
  "fake_data": {"balance": 1250000, "recipient": "Nguyen Van A"}
}
```

Validator (`ctcv_sandbox.validator`) từ chối khi: `start_screen` không tồn tại; màn hình không terminal mà không có `valid_actions`; action trỏ tới element/screen không tồn tại; màn hình không đến được từ `start_screen`; `success.screen` không terminal; `coach_line` > 2 câu hoặc chứa thuật ngữ trong `config/guardrails.yaml: banned_terms`; bất kỳ element `kind: input` có id/label khớp `never_ask` mà `sensitive != true`; `app_label` thiếu "mô phỏng"; `never_ask` thiếu "otp" hoặc "mat_khau". Engine (`ctcv_sandbox.engine`): `start(spec) -> State`, `apply(state, event) -> (State, Feedback)`; Feedback gồm `hint`, `mistake: bool`, `done: bool`; đếm steps/mistakes/hints.

12 kịch bản (id cố định): E02: `chuyen-khoan-qr`, `dang-nhap-vneid`, `xac-nhan-cu-tru`, `ke-khai-doanh-thu`; E10: `xuat-trinh-giay-to`, `khai-sinh-truc-tuyen`, `kiem-tra-bien-dong-so-du`, `cai-app-kho-chinh-thuc`, `doi-mat-khau`, `bat-xac-thuc-2-lop`, `thanh-toan-qr-cua-hang`, `goi-video-zalo`. E01 giao 1 kịch bản mẫu hoàn chỉnh `chuyen-khoan-qr.json` (level 1) qua validator.

## 6. Schema kịch bản lừa đảo (`ctcv_drills.schema`, `config/schemas/drill.schema.json`)

`key` (slug), `channel` (sms|zalo|call), `impersonates` (enum nhãn: cong-an, thue, ngan-hang, shipper, trung-thuong, nguoi-than, dien-luc, buu-dien), `pretext` (1 câu mô tả tình huống, ≤ 30 từ, không phải lời thoại), `red_flags[]` (mã từ danh mục: giuc-chuyen-tien, doi-otp, xung-co-quan, link-la, doa-dam, yeu-cau-cai-app, giu-bi-mat, tai-khoan-la), `options[]` (3–4 lựa chọn `{id, text, correct: bool}` đúng 1 correct), `debrief` (≤ 2 câu), `three_things` (đúng 3 mục), `label` = "Đây là mô phỏng", `variant` (1..5), `severity` (1..3). Rule chặn: không có trường `script`/`dialogue`/`message`; không chuỗi nào > 200 ký tự; `pretext` không chứa số tài khoản/link. E01 giao 1 mẫu `gia-danh-cong-an-goi-dien.json`.

## 7. Tool của agent (`ctcv_agent.tools`, whitelist đóng trong `config/tools.yaml`)

`get_session_state(session_id)`, `next_step(session_id)`, `search_guides(query, skill)`, `verify_citation(claim, doc_id)`, `start_drill(key)`, `grade_drill(drill_id, option_id)`, `log_progress(user_id, skill, level)`, `escalate_to_volunteer(reason)`. Mỗi tool: module riêng, `Input`/`Output` Pydantic, hàm `run(inp) -> Output`, `SIDE_EFFECT: Literal["none","sandbox","log"]`. `TOOL_REGISTRY` là `MappingProxyType`; router chỉ gọi tool có trong registry **và** trong yaml; tên lạ → `ToolNotAllowed`. Test bất biến: không tool nào có side effect ngoài `none|sandbox|log`; không module tool nào import `httpx`/`requests`/`subprocess`.

Planner output: `PlannerOutput{say: str (≤2 câu), action_hint: {element_id, color, label}|null, tool_calls: [{name, args}], confidence: float 0..1}`. Guardrails (`ctcv_agent.guardrails`): `redact_pii(text)`, `refuses_sensitive_request(text) -> bool` (OTP/mật khẩu/số thẻ/CCCD), `refuses_real_action(text) -> bool` ("làm giúp tôi trên app thật", "chuyển tiền giúp"), `enforce_style(say, first_turn) -> StyleVerdict{ok, reasons}` (≤2 câu, có hành động cụ thể, xác nhận ý định lượt đầu, không thuật ngữ), `requires_citation(answer, citations) -> bool`. Ngưỡng và regex trong `config/guardrails.yaml`.

## 8. Config (`config/*.yaml`, mỗi file có JSON Schema trong `config/schemas/` và test `tests/config/`)

- `app.yaml`: ports, `screen_ttl_seconds: 60`, `log_retention_days: 30`, `rate_limit_per_min`, `max_concurrent_sessions`, `ui.min_font_pt: 20`, `ui.min_tap_px: 56`, viewports e2e `[360x800, 390x844, 412x915]`.
- `models.yaml`: `planner: Qwen/Qwen3.5-9B` (adapter LoRA, quant awq), `planner_small: Qwen/Qwen3.5-2B` (gguf Q4_K_M), `vlm: Qwen/Qwen3-VL-8B-Instruct`, `asr: vinai/PhoWhisper-small` / `asr_small: vinai/PhoWhisper-tiny`, `tts: TBD-ADR-002` (ứng viên: F5-TTS-Vietnamese, viXTTS, Piper vi), `embed: BAAI/bge-m3`, `rerank: BAAI/bge-reranker-v2-m3`, `ui_detector: yolox-tiny (nội bộ)`; mỗi mục có `endpoint`, `license`, `confidence_threshold`.
- `tools.yaml`: 8 tool + side_effect.
- `guardrails.yaml`: regex PII (CCCD 12 số, số thẻ 16 số, OTP 4–8 số sau từ "otp/mã"), từ khóa cấm, `banned_terms` (thuật ngữ: "xác thực", "token", "đăng xuất"…, có bản thay thế), `max_sentences: 2`, `escalate_confidence: 0.6` (câu hỏi mở E05: 0.6 hay 0.7).
- `eval.yaml`: ngưỡng chấp nhận/chặn theo plan §7 (6 bộ).
- `prompts/coach.v1.md`, `quarantine.v1.md`, `vlm_screen.v1.md`, `judge.v1.md`: có header YAML `version`, `model`, `purpose`.

## 9. Registry (`data/registry/*.yaml`, schema trong `config/schemas/`)

`datasets.yaml[]`: name, version, source (url|synthetic), license, collected_at, size{records, mb}, sha256, used_for (rag|sft|dpo|ui|drill|eval), pii (none), notes. `models.yaml[]`: name, base, license, adapter_path, quantization, eval_report, served_at, card. Khởi tạo với các mục đã biết (giấy phép đúng: Qwen3.5 Apache-2.0, Qwen3-VL Apache-2.0, PhoWhisper BSD-3-Clause, bge-m3 MIT, YOLOX Apache-2.0, Common Voice vi CC0, VIVOS CC BY-NC-SA 4.0 — chỉ đánh giá, không huấn luyện phát hành).

## 10. Makefile (SHELL := bash; chạy được trên Git Bash Windows và Linux)

`install` (uv sync + pnpm install + pre-commit install + playwright install chromium khi `E2E=1`), `doctor [GPU=1]`, `dev`, `schemas`, `lint`, `format`, `unit`, `integration`, `e2e`, `eval [QUICK=1]`, `redteam` (guardrail thuần, không model), `redteam-model`, `loadtest`, `audit` (gitleaks detect, pip-audit, pnpm audit, allowed-deps + giấy phép), `build` (docker compose build), `check` (= lint unit integration redteam audit docs-check, thêm e2e và build khi `QUICK≠1`; **không** gọi eval/model — v2 D13), `gate` (= eval QUICK=1 + redteam-model + loadtest; cần GPU/staging; hằng đêm và trước tag), `release-check` (= check + gate + a11y + CHANGELOG/ADR/prompt log), `data`, `train`, `deploy ENV=`, `rollback TAG=`, `failover`, `backup`, `restore-drill`, `pilot-kit`, `pilot-report`, `dossier [DRAFT=1]`, `promptlog-sync`, `promptlog-export` (kèm redaction gate D21), `evidence` (chụp ảnh minh chứng + snapshot DAILY vào `docs/screens/YYYY-MM-DD/`), `declaration`, `plugin`, `daily`. Target chưa hiện thực in "CHƯA HIỆN THỰC — epic EXX" và **exit 0** chỉ khi target đó chưa nằm trong `check`; mọi thứ trong `check` phải thật. `make check` ghi `docs/status/last_check.json` {ts, git_head, ok}.

Trên Windows: `make` từ winget `ezwinports.make`, đường dẫn `%LOCALAPPDATA%\Microsoft\WinGet\Links`; README ghi rõ.

## 11. `.claude/` (khớp docs/prompt.md §2, §3, §9 với các sửa đổi D2–D4)

- `settings.json` (v2): `"model": "claude-fable-5-1"`, `"effortLevel": "xhigh"`; **không** có `CLAUDE_CODE_SUBAGENT_MODEL` hay hai biến MAX_* (không tồn tại); `"enableAllProjectMcpServers": false`, `"enabledMcpjsonServers": ["playwright"]`; `permissions.defaultMode: acceptEdits`; allow: `Bash(make *)`, `Bash(uv *)`, `Bash(pnpm *)`, `Bash(npx *)`, `Bash(python *)`, `Bash(pytest *)`, `Bash(ruff *)`, `Bash(docker compose *)`, `Bash(git status*)`, `Bash(git diff*)`, `Bash(git log*)`, `Bash(git add *)`, `Bash(git commit *)`, `Bash(git checkout -b *)`, `Bash(git merge *)`, `Bash(git worktree *)`, `Bash(git push origin epic/*)`, `Bash(gh *)`, `mcp__playwright`; deny: `Bash(git push --force*)`, `Bash(git push -f*)`, `Bash(* --no-verify*)`, `Bash(rm -rf *)`, `Bash(docker system prune*)`, `Read(.env)`, `Read(.env.*)`, `Read(**/*.pem)`, `Read(docs/dossier/private/**)`, `Edit(docs/prompt-log/**)`, `Write(docs/prompt-log/**)`, `MultiEdit(docs/prompt-log/**)`, `Edit(data/registry/*.lock)`, `Write(data/registry/*.lock)`. Hooks: SessionStart→session-start, UserPromptSubmit→prompt-guard, PreToolUse `Bash`→guard, PreToolUse `Edit|MultiEdit|Write|NotebookEdit`→protect-paths, PostToolUse `Edit|MultiEdit|Write|NotebookEdit`→format (timeout 120), PostToolUseFailure `Bash`→notify, SubagentStop→subagent-log (+ chép agent transcript, D20), PreCompact→checkpoint, Stop→promptlog + daily, SessionEnd→promptlog --close. Lệnh hook: `bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh" <name> [args]`. Marker `.claude/BOOTSTRAP` (D22) tồn tại trong E01.
- `hooks/run.sh`: chọn `python3` (≥3.10) rồi `python`; `exec` file `.py` cùng tên; stdin JSON đi thẳng qua. Mỗi `.py`: đọc JSON từ stdin, không phụ thuộc thư viện ngoài, exit 2 để chặn (in lý do tiếng Việt ra stderr), exit 0 bình thường.
  - `guard.py`: chặn `rm -rf`, `git push --force`, `git reset --hard origin`, `docker system prune`, `mkfs`, fork bomb, `curl|sh`; chặn đọc `.env` qua cat/less/head/tail/grep/type/Get-Content; nếu lệnh khớp `make train|python .*train` → gọi `budget.py` (đọc `training/budget.json`, chặn khi job dự kiến > 20 giờ GPU hoặc chi phí API > 500.000 đ).
  - `protect-paths.py`: chặn Edit/Write vào `docs/prompt-log/**`, `data/registry/*.lock`, `services/api/alembic/versions/*` đã merge (có trong `git log main`), `config/eval.yaml` trừ khi biến `CTCV_ALLOW_EVAL_THRESHOLD=1`.
  - `format.py`: chạy `ruff format`/`ruff check --fix` cho `.py`, `prettier --write` cho web; chạy test nhanh của module (pytest -q -x thư mục tests gần nhất, timeout 60 s); lỗi in ra stdout để Claude thấy.
  - `promptlog.py`: copy `transcript_path` → `docs/prompt-log/<YYYY-MM-DD>-<session8>.jsonl` (ghi đè cùng phiên → 1 file/phiên, không trùng); cập nhật `INDEX.md` (ts, file, sha256, git head); `--close` đánh dấu đóng. `session-start.py` ngoài việc in DAILY/CHECKPOINT/last_check còn **quét** `~/.claude/projects/<slug>/*.jsonl` và nhập transcript phiên trước chưa có trong INDEX (bù cho phiên không có hook).
  - `daily.py` (Stop): nếu có thay đổi mã (git status) mà `last_check.json` cũ hơn → in nhắc (không chặn); cập nhật mục "Phiên gần nhất" trong `docs/status/DAILY.md`.
  - `prompt-guard.py`: chặn prompt chứa mẫu token/khóa (`sk-`, `ghp_`, `hf_`, `AKIA`, chuỗi base64 dài ≥ 40 sau từ key/secret/token); ghi prompt (đã che) vào `docs/status/prompts.log`.
  - `notify.py`, `subagent-log.py`, `checkpoint.py`, `budget.py` như prompt.md mô tả.
- `agents/` (v2): 10 file theo bảng prompt.md §2 (architect, backend-dev, frontend-dev, data-engineer, ml-trainer, qa-tester, security-redteam, devops, reviewer, docs-writer) với `tools`, **`model: inherit`** (D17), `effort`, `skills`, `isolation: worktree` (backend-dev, frontend-dev — chỉ sau commit đầu, D18), **không** `background` (D18), `memory: project` (architect, security-redteam, reviewer), `permissionMode: plan` (architect, read-only, trả nội dung ADR — D19), `reviewer` tools = Read, Grep, Glob (D19), `security-redteam` tools = Read, Grep, Glob, Bash, Write, Edit (ghi chỉ trong `eval/redteam/**`, `docs/security/**` — ép bằng protect-paths), `disallowedTools: Read(.env)` (devops), `color`. Tùy chọn `eval-runner` (`background: true`, Read/Bash) cho eval đêm.
- `skills/`: ctcv-conventions, fastapi-conventions, elder-ui, coach-style, data-pipeline, training-runbook, test-strategy, agent-security, dossier-btc (`disable-model-invocation: true`), hackathon-kit (`disable-model-invocation: true`), epic, daily, review, fix, refactor, incident (6 skill quy trình có `argument-hint`, `disable-model-invocation: true`). Nội dung lấy từ prompt.md §5–§6 và §9.
- `.mcp.json` (v2, D24): chỉ `playwright` — `{"mcpServers":{"playwright":{"type":"stdio","command":"cmd","args":["/c","npx","-y","@playwright/mcp@latest","--headless"]}}}` (máy dev Windows; Linux/CI thêm ở user scope bằng `claude mcp add playwright -- npx -y @playwright/mcp@latest --headless`). GitHub qua `gh` CLI; postgres read-only ghi BACKLOG.
- `plugins/ctcv-kit/`: sinh bằng `scripts/sync_plugin.py` (copy agents/skills/hooks, bỏ `hooks`/`mcpServers`/`permissionMode` khỏi frontmatter agent, `hooks/hooks.json` từ settings).

## 12. CLAUDE.md (≤ 150 dòng)

Nội dung Phụ lục A plan §13 + mục "Delegation" (6 quy tắc prompt.md §2) + mục "Máy dev Windows" (Git Bash, make từ winget, không dùng jq) + "Lệnh chuẩn" + tham chiếu `docs/competition/BTC-2026-yeu-cau.md` và `docs/decisions/E01-brief.md`. Không import `@file` để tránh phình ngữ cảnh.

## 13. Epic files (`epics/`)

E01…E12 theo bảng plan §6, cấu trúc Phụ lục B (Mục tiêu · Đầu vào · Công việc · Đầu ra · Test nghiệm thu · Không được làm · Câu hỏi mở ≤ 3 · Checklist ≤ 30 phút). Thêm `PILOT.md` và `DOSSIER.md` cho hai hàng cuối của bảng. DOSSIER.md bám 13 mục MẪU 3 và 6 thành phần BTC; ghi rõ Google Drive cho prompt log. Mỗi epic ghi rõ lệnh test chạy được (`make …` hoặc `uv run pytest path`).

## 14. Docs

- `decisions/`: `ADR-000-template.md`, `ADR-001-kien-truc-stack.md`, `ADR-002-chon-model.md` (kèm câu hỏi mở gộp planner+VLM, chọn TTS), `ADR-003-sandbox-thay-vi-he-thong-that.md`, `ADR-004-tach-planner-quarantine.md`, `ADR-005-chinh-sach-du-lieu-ttl-anh.md`, `BACKLOG.md`.
- `status/DAILY.md` (mẫu KPI plan §11), `status/CHECKPOINT.md`.
- `prompt-log/README.md` (quy tắc: không sửa tay, hash, Drive), `INDEX.md` (bảng rỗng có header).
- `dossier/src/00-thong-tin-doi.md`, `01-…13-….md` (tên mục nguyên văn MẪU 3; nội dung khung lấy từ idea.md với placeholder `{{eval:<key>}}` cho số liệu), `dossier/build/build_dossier.py` (python-docx điền mẫu → docx; PDF qua LibreOffice nếu có, nếu không in hướng dẫn), `dossier/README.md`.
- `ops/RUNBOOK.md` (khung theo plan §8), `ops/incidents.md`.
- `pilot/README.md` (thiết kế plan §9, chờ `make pilot-kit`).

## 15. Kiểm thử E01 (phải xanh khi kết thúc)

- `uv run pytest` từ gốc: mọi gói; coverage ≥ 80% cho `ctcv_agent`, `ctcv_sandbox`, `ctcv_api` (skeleton nhỏ nên đạt được).
- `tests/invariants/`: (a) tool whitelist + không side effect; (b) không PII trong fixtures/log mẫu + model DB không có cột CCCD/OTP/password; (c) `requires_citation` bắt câu dữ kiện không nguồn.
- `tests/config/`: mọi yaml qua schema; `models.yaml` không có model ngoài danh sách; `tools.yaml` == registry.
- Sandbox: validator từ chối ≥ 8 kịch bản lỗi (fixtures); engine đi trọn `chuyen-khoan-qr`.
- Drills: validator từ chối kịch bản có lời thoại hoàn chỉnh.
- API: contract test 16 route; `/v1/scenarios` trả kịch bản mẫu; `/health` 200.
- Red-team: `make redteam` chạy 50 kịch bản qua guardrails thuần (không cần model) = 0 lỗi.
- Web: `pnpm -C apps/web lint && test` (vitest: token cỡ chữ ≥ 20 pt, vùng bấm ≥ 56 px); Playwright e2e smoke chỉ chạy khi `E2E=1`.
- `make check QUICK=1` xanh trên máy dev; `make check` đầy đủ trong CI (docker build).

## 16. Phân gói việc cho dựng khung song song (mỗi gói chỉ ghi vào thư mục mình sở hữu)

| WP | Thư mục sở hữu | Ghi chú |
| --- | --- | --- |
| F (foundation, chạy trước) | gốc: pyproject/uv workspace, pnpm-workspace, package.json, Makefile, .gitignore, .gitattributes, .editorconfig, .dockerignore, .env.example, .python-version, .pre-commit-config.yaml, LICENSE, SECURITY.md, CHANGELOG.md, README.md; `libs/core`; `config/`; `tests/conftest.py`, `tests/config/`; `scripts/` | Tạo `uv.lock` bằng `uv lock`; mọi gói khác là member đã khai báo trước (thư mục có thể chưa có mã) |
| A | `.claude/`, `.mcp.json`, `CLAUDE.md`, `plugins/ctcv-kit/`, `scripts/sync_plugin.py` | hook Python + run.sh; test hook bằng `python -m pytest .claude/hooks/tests` |
| B | `epics/`, `docs/decisions/`, `docs/status/`, `docs/prompt-log/`, `docs/ops/`, `docs/pilot/`, `docs/screens/`, `hackathon/` | |
| C | `services/agent/`, `tests/invariants/` | |
| D | `services/api/` | |
| E | `sandbox/`, `drills/` | |
| G | `services/speech/`, `services/vision/`, `apps/web/`, `apps/android/` | |
| H | `data/`, `training/`, `eval/` | red-team 50 kịch bản + runner dùng `ctcv_agent.guardrails` |
| I | `deploy/`, `.github/` | Dockerfile tất cả dịch vụ; compose; CI |
| J | `docs/dossier/` | 13 mục + build script |
| K (tích hợp, chạy sau) | toàn repo | `uv sync`, `make check QUICK=1`, sửa xung đột, `make build`; áp dụng §17 cho các gói đã viết trước v2 |

## 17. Điều chỉnh sau rà soát (v2) — checklist bắt buộc cho tích hợp và review

Nguồn: `docs/analysis/2026-09-18-review-findings.md` (70 phát hiện đã kiểm chứng, 21 khoảng trống). Các gói viết trước v2 (F, và bất kỳ gói nào đọc brief v1) phải được rà theo danh sách này ở bước tích hợp K và bước review:

1. Makefile: `check` không gọi `eval`; thêm `gate`, `redteam-model`, `promptlog-sync`, `evidence`, `doctor GPU=1` (D13, D20, D29).
2. `config/models.yaml`: `vlm` = cùng `Qwen/Qwen3.5-9B` (D9 v2, trạng thái "đề xuất"); `planner_small: Qwen/Qwen3.5-2B` với vai trò "đường CPU (llama.cpp) cho dev/hackathon/fallback" (D29); thêm `quarantine` và `judge` (cùng base 9B, prompt riêng, không tool — SEC-03); mọi mục có `license` SPDX + `license_url`.
3. `config/allowed-deps.yaml` + kiểm tra trong `make audit` (D26). Danh sách khởi đầu = mọi dependency trong `uv.lock`/`pnpm-lock.yaml` của E01 với giấy phép; cấm AGPL/GPL/CC-NC ở runtime.
4. `data/registry/datasets.yaml` schema: thêm `redistribute`, `derived_from`, `source_type`, `tos_checked_on`, `generator_model`, `generator_license`, `tos_url` (LIC-08/09/10); `models.yaml`: `license_url`, `card`.
5. `docs/legal/refs.yaml` (số hiệu, tên, ngày hiệu lực, điều khoản, url, `verified_on`, `verified_by`); dossier non-draft fail khi PDF nhắc số hiệu chưa `verified_on` (LEG-11). Đã xác minh 18/9: Luật 134/2025/QH15 (hiệu lực 1/3/2026), NĐ 142/2026/NĐ-CP (1/5/2026). Chưa xác minh: TT 05/2026/TT-BKHCN, Luật 91/2025/QH15, NĐ 356/2025/NĐ-CP.
6. `.claude/`: D17–D24 (inherit, không background, protect `.claude/**` với marker, guard mở rộng, promptlog theo session, MCP cmd /c, effortLevel).
7. `services/agent`: quarantine schema kín; `user_id` không phải tham số tool (lấy từ ngữ cảnh phiên); tests bất biến thứ 4: không chuỗi tự do từ nguồn untrusted vào prompt planner (taint) (SEC-03).
8. `services/api`: `events.payload_json` allowlist theo type; `display_name` = mã/biệt danh; `qr_token` có `expires_at` + `revoked_at`; không endpoint liệt kê drills (SEC-04, SEC-06).
9. `drills`: trường `utterance` theo D27; validator cấm URL/SĐT/STK/tên thật.
10. `deploy`: profiles `cpu`/`gpu`; `models` dùng image vLLM upstream (không build); Cloudflare DNS-only nếu cam kết "máy chủ trong nước" (ETH-12); staging HTTPS (Caddy hoặc `cloudflared`) là điều kiện tiên quyết của E04 (N03).
11. Tài liệu: ADR-006 (lịch 3 pha, pilot hai tầng, cắt APK→PWA offline, kèm cặp trên app thật → hướng phát triển) ở trạng thái "đề xuất, chờ người dùng"; epics ghi "Mốc thực tế"; DOSSIER dùng 13 mục MẪU 3 + Drive; `docs/dossier/private/team.yaml`.
12. Errata sự kiện ở cuối `docs/idea.md`, `docs/plan.md`, `docs/prompt.md` (D31), không sửa thân văn bản.
13. Việc **người dùng** phải làm hôm nay (không phải Claude): gọi Đoàn trường/Phòng CTSV TDTU + BTC về hạn nội bộ, ai upload 6 thành phần, có được cập nhật hồ sơ trước chung kết (N02); chốt 3 thành viên cùng trường, ≤ 22 tuổi, rảnh 10–11/10 và 20–22/11 (N08); nộp đơn giấy xác nhận SV; thuê GPU (SSH + nvidia-smi trước 20/9); GitHub Pro/Student Pack cho branch protection; xuất hội thoại đã soạn 3 tài liệu vào `docs/prompt-log/pre-D1/` (N14); tạo commit đầu tiên (CC-11).
