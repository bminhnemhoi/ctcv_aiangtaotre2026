# ADR-001 — Kiến trúc và stack

Ngày: 2026-09-18 · Người quyết: orchestrator E01 theo `E01-brief.md` v2 (D1–D6, D13–D16, D22–D26, D29) · Trạng thái: **chốt cho E01** (thay đổi sau qua ADR mới) · Liên quan: plan §5, idea §5, prompt §2–3; C06, C10, F10, F11, N07, N11, CC-06

## Bối cảnh
Ba file nguồn định nghĩa cây thư mục ở ba nơi khác nhau (C06), giả định máy dev Ubuntu + GPU trong khi máy thật là Windows 11/Git Bash không GPU (C10/F11), gộp eval có model vào cổng PR (F10), và không nói mã dùng chung ở đâu. Cần một kiến trúc cố định để nhiều agent dựng khung song song.

## Lựa chọn
- **6 dịch vụ** (plan §5): `web` (`apps/web`, Vite + React 18 + TS + Tailwind, PWA), `api` (`services/api`, FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2), `agent` (`services/agent`: planner, quarantine, tool router, guardrails, verify), `speech` (`services/speech`: faster-whisper + TTS cache), `vision` (`services/vision`: VLM client, che PII; YOLOX-Tiny ONNX giữ skeleton), `models` (`deploy/models`: vLLM image upstream, profile `gpu`; llama.cpp server profile `cpu` — D29). Hạ tầng: PostgreSQL 16, Redis 7, Qdrant 1.x, MinIO (ảnh TTL 60 s), Caddy 2, Uptime Kuma; Prometheus/Grafana chỉ khi còn thời gian (F13, BACKLOG).
- **Cây thư mục duy nhất** = `E01-brief.md` §1 (C06); không tạo thư mục ngoài đó khi chưa hỏi. Mỗi gói Python: `src/` layout, hatchling, `tests/` riêng.
- **uv workspace** một `uv.lock` ở gốc (10 gói `ctcv-*` → `ctcv_*`); **pnpm workspace** `apps/*`; `libs/core` (`ctcv_core`, D5): `load_config` có JSON Schema, `AppError` mã + thông điệp tiếng Việt, log JSON không PII, paths, text tiếng Việt.
- **Cổng chất lượng hai tầng** (D13, F10/S9/C04-gap): `make check` = tất định, không model (lint, unit, integration, contract API, schema config, bất biến, red-team guardrail thuần, audit, docs-check; + e2e và docker build khi `QUICK≠1`), chạy mỗi PR trên GitHub-hosted; `make gate` = cần GPU/staging (`eval QUICK=1` với LLM-judge, `redteam-model`, `loadtest`), hằng đêm trên self-hosted runner và trước tag. CI không bao giờ gọi model. Coverage ≥ 80 % `ctcv_core/ctcv_agent/ctcv_sandbox/ctcv_api` ép ở `make unit`.
- **Allow-list thư viện** = `config/allowed-deps.yaml` (D26/N07), kiểm ở `make audit`; cấm AGPL/GPL/CC-NC runtime, cấm `ultralytics`/`yolov5`. Ngoài stack brief §2, các extra của API được phép: `PyJWT` (MIT), `sse-starlette` (BSD-3), `prometheus-client` (Apache-2.0), `python-multipart` (Apache-2.0), `pydantic-settings` (MIT); dev/pipeline: `python-docx` (MIT), `pypdf` (BSD-3-Clause, trích PDF mặc định), `jsonschema`, `pytest-cov`, `pip-audit`, `testcontainers`, `k6` (binary), `pre-commit`; `pymupdf` (AGPL-3.0) **không** đưa vào khi chưa có ADR riêng — chỉ cân nhắc nếu `pypdf` không đọc được PDF nguồn, và khi đó chỉ ở bước pipeline, không vào image runtime.
- **Claude Code**: hook bằng **Python 3 stdlib** gọi qua `bash .claude/hooks/run.sh <tên>` (D2, không jq); Stop hook **không chặn** (D4) — cổng cứng ở `/epic` và CI; fail-closed cho guard/protect-paths (D22); protect `.claude/**`, `CLAUDE.md`, `.github/workflows/**`, `Makefile` trừ khi có marker `.claude/BOOTSTRAP` (N11); PostToolUse chỉ format (D23); `.mcp.json` chỉ `playwright` qua `cmd /c npx` trên Windows (D24).
- **Máy dev Windows 11** (Git Bash, `make` từ winget `ezwinports.make`, Docker Desktop, không GPU): Compose profile `cpu`; `VLLM_BASE_URL` trỏ máy GPU thuê (SSH tunnel/Tailscale) hoặc llama.cpp `Qwen3.5-2B` GGUF; `make doctor` = doctor-dev (không đòi GPU), `make doctor GPU=1` kiểm máy thuê qua SSH; docx→pdf bằng container LibreOffice. Unit test SQLite in-memory, integration PostgreSQL testcontainers từ E02 (D15). Tiếng Anh cho mã/commit, tiếng Việt cho UI/lỗi/tài liệu (D16).

## Hệ quả
- Mọi epic viết đường dẫn theo brief §1; `make check` luôn chạy được offline trong < 10 phút; eval/red-team có model chỉ có số liệu khi máy GPU sẵn (E05+).
- Thêm thư viện = sửa `config/allowed-deps.yaml` + PR (một lần duyệt), không hỏi từng câu.
- Rủi ro: self-hosted runner trên máy GPU cần bảo mật token; hook Python phải được test (`.claude/hooks/tests`); pymupdf AGPL phải bị chặn khỏi image runtime bởi `make audit`.

## Trạng thái
2026-09-18 chốt cho E01 theo brief v2. Xem lại khi: vLLM không hỗ trợ Qwen3.5 (→ ADR-002 phương án B), hoặc BTC yêu cầu nền tảng khác ở hackathon (kit dùng profile `cpu`).
