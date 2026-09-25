# CTCV - Makefile (brief section 10 v2, D13). Runs under Git Bash on Windows and under Linux.
# Rules: recipes are plain POSIX bash and ASCII-only (GNU make from winget passes recipe text
# through the ANSI code page, so Vietnamese text inside a recipe would arrive garbled);
# user-facing messages go through scripts/msg.py; timestamps/hashes go through Python.
# Targets inside `check` are real; later-epic targets print "CHUA HIEN THUC - xem epics/EXX.md"
# and exit 0. `make check` = deterministic, model-free gate; `make gate` = needs GPU/staging.
SHELL := bash
.SHELLFLAGS := -eo pipefail -c
.DEFAULT_GOAL := help
.NOTPARALLEL:

UV ?= uv
PNPM ?= pnpm
COMPOSE_FILE ?= deploy/docker-compose.yml
COMPOSE = docker compose -f $(COMPOSE_FILE)
QUICK ?= 0
ENV ?= staging
E2E ?= 0
GPU ?= 0
DRAFT ?= 0
TAG ?=
COV_FAIL_UNDER ?= 80
COMPOSE_PROFILES ?= cpu
PIP_AUDIT_REQ := .pip-audit-requirements.txt

export PYTHONUTF8 := 1
export PYTHONIOENCODING := utf-8
export QUICK E2E COMPOSE_PROFILES

# Python without the project env (works before `make install`, never triggers a sync).
PY0 := $(UV) run --no-project python
MSG := $(PY0) scripts/msg.py
RUN_IF := $(UV) run python scripts/run_if_exists.py
QUICK_FLAG := $(if $(filter 1,$(QUICK)),--quick,)
GPU_FLAG := $(if $(filter 1,$(GPU)),--gpu,)
DRAFT_FLAG := $(if $(filter 1,$(DRAFT)),--draft,)

define NOT_IMPLEMENTED
$(MSG) not-implemented $(1)
endef

.PHONY: help install doctor dev schemas lint format unit integration e2e eval redteam redteam-model \
        loadtest audit build docs-check check gate release-check data train deploy rollback failover \
        backup restore-drill pilot-kit pilot-report dossier promptlog-sync promptlog-export evidence \
        declaration plugin daily

help: ## Liet ke target (mo ta tieng Viet co dau doc tu file nen hien dung)
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "} {printf "  %-18s %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------- setup
install: ## uv sync --all-packages + pnpm install + pre-commit install (+ playwright chromium khi E2E=1)
	$(UV) sync --all-packages
	@if [ -f package.json ]; then $(PNPM) install; fi
	@if [ -d .git ]; then $(UV) run pre-commit install && $(MSG) precommit-installed; fi
	@if [ "$(E2E)" = "1" ]; then \
	  if [ -f apps/web/package.json ]; then $(PNPM) -C apps/web exec playwright install chromium; \
	  else $(MSG) e2e-no-web; fi; fi

doctor: ## Kiểm tra máy dev (GPU=1: kiểm thêm máy GPU qua SSH — D29)
	@if command -v $(UV) >/dev/null 2>&1; then $(PY0) scripts/doctor.py $(GPU_FLAG); \
	else python3 scripts/doctor.py $(GPU_FLAG) || python scripts/doctor.py $(GPU_FLAG); fi

dev: ## Chạy toàn bộ dịch vụ dev (Docker Compose, profile $(COMPOSE_PROFILES))
	@if [ -f deploy/docker-compose.dev.yml ]; then $(COMPOSE) -f deploy/docker-compose.dev.yml up --build; \
	elif [ -f $(COMPOSE_FILE) ]; then $(COMPOSE) up --build; \
	else $(call NOT_IMPLEMENTED,E01); $(MSG) compose-missing; fi

schemas: ## Xuất JSON Schema từ model Pydantic (sandbox, drills) vào config/schemas
	$(UV) run python scripts/gen_schemas.py

# ----------------------------------------------------------------------------- quality gates (in `check`)
lint: ## ruff check + ruff format --check (+ pnpm -r lint khi có apps/web)
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	@if [ -f apps/web/package.json ]; then $(PNPM) -r --if-present lint; fi

format: ## ruff format + ruff check --fix (+ prettier khi có apps/web)
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	@if [ -f apps/web/package.json ] && [ -x node_modules/.bin/prettier ]; then $(PNPM) exec prettier --write "apps/**/*.{ts,tsx,js,jsx,json,css,md}"; fi

unit: ## pytest (trừ integration/e2e) + coverage >= $(COV_FAIL_UNDER)% cho ctcv_core/agent/sandbox/api
	$(UV) run pytest -m "not integration and not e2e" -p no:cacheprovider \
	  --cov --cov-report=term-missing:skip-covered --cov-fail-under=$(COV_FAIL_UNDER)

integration: ## pytest -m integration (mã thoát 5 = chưa có test → OK)
	@set +e; $(UV) run pytest -m integration -p no:cacheprovider; rc=$$?; set -e; \
	if [ $$rc -eq 5 ]; then $(MSG) no-integration-tests; exit 0; fi; exit $$rc

e2e: ## Playwright 3 viewport (chỉ chạy khi E2E=1)
	@if [ "$(E2E)" != "1" ]; then $(MSG) skip-e2e; \
	elif [ -f apps/web/package.json ]; then $(PNPM) -C apps/web run e2e; \
	else $(call NOT_IMPLEMENTED,E02); fi

redteam: ## Red-team qua guardrails thuần (không model) — thuộc `check`
	$(RUN_IF) ctcv_eval.redteam

audit: ## gitleaks + allowed-deps/giấy phép (D26) + pip-audit + pnpm audit
	@if command -v gitleaks >/dev/null 2>&1; then gitleaks detect --no-git --source . --redact --exit-code 1 --no-banner && $(MSG) gitleaks-clean; \
	else $(MSG) gitleaks-missing; fi
	$(UV) run python scripts/check_deps.py
	@set +e; $(UV) export --format requirements-txt --no-emit-workspace --no-hashes -o $(PIP_AUDIT_REQ) >/dev/null \
	  && $(UV) run pip-audit -r $(PIP_AUDIT_REQ) --no-deps --progress-spinner off; rc=$$?; set -e; rm -f $(PIP_AUDIT_REQ); exit $$rc
	@if [ -f apps/web/package.json ]; then $(PNPM) audit --audit-level high; fi

build: ## docker compose build (Dockerfile ở deploy/docker/*.Dockerfile)
	@if [ -f $(COMPOSE_FILE) ]; then $(COMPOSE) build; else $(call NOT_IMPLEMENTED,E01); $(MSG) compose-missing; fi

docs-check: ## README đủ mục, CHANGELOG có [Unreleased], docs/prompt-log/INDEX.md có mặt
	$(UV) run python scripts/check_docs.py

ifeq ($(QUICK),1)
CHECK_STEPS := lint unit integration redteam audit docs-check
else
CHECK_STEPS := lint unit integration e2e build redteam audit docs-check
endif

check: $(CHECK_STEPS) ## Cổng chất lượng tất định, không gọi model (QUICK=1: bỏ e2e + build). Ghi docs/status/last_check.json
	$(UV) run python scripts/write_last_check.py $(QUICK_FLAG)
	@$(MSG) check-green $(QUICK)

# ----------------------------------------------------------------------------- gates needing GPU/staging
eval: ## Bộ đánh giá 6 suite, cần model (QUICK=1: 100 mẫu). Thuộc `gate`, không thuộc `check`
	$(RUN_IF) ctcv_eval.harness $(QUICK_FLAG)

redteam-model: ## Red-team có model (200 kịch bản) — thuộc `gate`
	$(RUN_IF) ctcv_eval.redteam --with-model

loadtest: ## k6/Locust 50 người đồng thời, p95 < 2,5 s
	$(RUN_IF) ctcv_eval.loadtest

gate: ## Cổng cần GPU/staging: eval QUICK=1 + redteam-model + loadtest (hằng đêm, trước tag)
	$(MAKE) eval QUICK=1
	$(MAKE) redteam-model
	$(MAKE) loadtest

release-check: check gate ## Trước tag: check + gate + a11y + CHANGELOG/ADR/prompt log
	@if [ -f apps/web/package.json ]; then $(PNPM) -C apps/web run --if-present a11y; else $(MSG) a11y-missing; fi
	$(UV) run python scripts/promptlog_export.py --verify-only

# ----------------------------------------------------------------------------- data / training / ops (later epics)
data: ## Pipeline dữ liệu (crawl → chuẩn hóa → sinh → lọc → registry)
	$(RUN_IF) ctcv_data.pipeline

train: ## SFT → DPO → lượng tử hóa → YOLOX (ghi training/runs, model card)
	$(RUN_IF) ctcv_training

deploy: ## Triển khai ENV=staging|prod
	@if [ -f deploy/scripts/deploy.sh ]; then bash deploy/scripts/deploy.sh $(ENV); else $(call NOT_IMPLEMENTED,E12); fi

rollback: ## Quay lui TAG=vX.Y
	@test -n "$(TAG)" || { $(MSG) need-tag; exit 2; }
	@if [ -f deploy/scripts/rollback.sh ]; then bash deploy/scripts/rollback.sh $(TAG); else $(call NOT_IMPLEMENTED,E12); fi

failover: ## Chuyển DNS sang máy dự phòng
	@if [ -f deploy/scripts/failover.sh ]; then bash deploy/scripts/failover.sh; else $(call NOT_IMPLEMENTED,E12); fi

backup: ## PostgreSQL dump + Qdrant snapshot
	@if [ -f deploy/scripts/backup.sh ]; then bash deploy/scripts/backup.sh; else $(call NOT_IMPLEMENTED,E12); fi

restore-drill: ## Diễn tập khôi phục backup
	@if [ -f deploy/scripts/restore_drill.sh ]; then bash deploy/scripts/restore_drill.sh; else $(call NOT_IMPLEMENTED,E12); fi

pilot-kit: ## Tài liệu buổi pilot (phiếu đồng thuận, checklist)
	$(RUN_IF) ctcv_eval.pilot kit

pilot-report: ## Báo cáo pilot từ log
	$(RUN_IF) ctcv_eval.pilot report

# ----------------------------------------------------------------------------- dossier & evidence
dossier: ## Sinh hồ sơ BTC vào docs/dossier/out (DRAFT=1: bản nháp)
	@if [ -f docs/dossier/build/build_dossier.py ]; then $(UV) run python docs/dossier/build/build_dossier.py $(DRAFT_FLAG); \
	else $(call NOT_IMPLEMENTED,DOSSIER); fi

promptlog-sync: ## Nhập transcript từ ~/.claude/projects chưa có trong INDEX (hook promptlog --sync)
	@if [ -f .claude/hooks/promptlog.py ]; then bash .claude/hooks/run.sh promptlog --sync; else $(call NOT_IMPLEMENTED,E01); fi

promptlog-export: ## Kiểm hash + redaction gate (D21) → docs/dossier/out/07_PromptLog.zip
	$(UV) run python scripts/promptlog_export.py

evidence: ## Ảnh/snapshot minh chứng vào docs/screens/YYYY-MM-DD
	$(UV) run python scripts/evidence.py

declaration: ## Bản kê khai AI/dữ liệu/thư viện → docs/dossier/out/06_KeKhaiAI.md
	$(UV) run python scripts/declaration.py

plugin: ## Đóng gói plugins/ctcv-kit từ .claude (scripts/sync_plugin.py — WP A)
	@if [ -f scripts/sync_plugin.py ]; then $(UV) run python scripts/sync_plugin.py; else $(call NOT_IMPLEMENTED,E01); fi

daily: ## Cập nhật docs/status/DAILY.md (hook daily)
	@if [ -f .claude/hooks/daily.py ]; then echo '{}' | bash .claude/hooks/run.sh daily; else $(call NOT_IMPLEMENTED,E01); fi
