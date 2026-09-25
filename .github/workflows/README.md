# .github/workflows — CI/CD của CTCV (brief D13 v2)

| Workflow | Kích hoạt | Runner | Việc | Gọi model? |
| --- | --- | --- | --- | --- |
| `check.yml` | mọi pull request; push `main`; `workflow_call` từ `release.yml` | `ubuntu-latest` | job `check` (`make check QUICK=1` + `uv run pytest deploy/tests`), `e2e` (`make e2e E2E=1`, Chromium cache, record/replay + agent stub), `build` (`docker compose --profile cpu build` với cache BuildKit `type=gha`, kiểm tổng dung lượng < 8 GB), `audit` (gitleaks-action + `make audit`). Artifact: `eval-reports`, `playwright-report` | **Không bao giờ** |
| `gate.yml` | cron `0 19 * * *` UTC = 02:00 giờ Việt Nam; *Run workflow*; PR gắn nhãn `needs-gpu` | `[self-hosted, gpu]` | `make gate` (eval QUICK=1 với LLM-judge, red-team có model, load test); artifact `gate-report-<run>`; Telegram khi đỏ; **không commit** | Có (trên máy GPU) |
| `release.yml` | tag `v*` | `ubuntu-latest` | `check` → build + push `ghcr.io/<owner>/ctcv-{api,agent,speech,vision,web}:<tag>` → `deploy/scripts/deploy.sh` (chỉ khi có secret `DEPLOY_HOST` + `SSH_KEY`; tag có `-` → staging, còn lại → prod) → GitHub Release | Không |

`nightly-eval.yml` của brief §1 đã được thay bằng `gate.yml` (cùng vai trò, đúng D13: eval cần GPU không chạy trên GitHub-hosted).

## Đăng ký runner GPU tự host (`gate.yml`)

Làm trên máy GPU thuê (đã có Docker + NVIDIA container toolkit + uv + pnpm + make + k6), như user `deploy`:

1. GitHub → *Settings → Actions → Runners → New self-hosted runner* → Linux x64; chạy các lệnh tải và `./config.sh --url https://github.com/<owner>/ctcv --token <token> --name gpu-01 --labels self-hosted,gpu --unattended --work /opt/ctcv-runner`. Nhãn `gpu` là bắt buộc (`runs-on: [self-hosted, gpu]`).
2. `sudo ./svc.sh install deploy && sudo ./svc.sh start` → runner hiện *Idle* trong trang Runners.
3. *Settings → Actions → General → Fork pull request workflows*: giữ mặc định (PR từ fork **không** chạy trên self-hosted); *Workflow permissions*: *Read repository contents*.
4. Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (thông báo gate đỏ). `.env` trên máy: `VLLM_BASE_URL=http://localhost:8040/v1` khi stack staging chạy cùng máy, `COMPOSE_PROFILES=gpu`.
5. *Actions → gate → Run workflow* để thử; bước đầu phải in được `nvidia-smi`.

Máy GPU bật theo lịch (RUNBOOK §7): run cron khi máy tắt sẽ ở trạng thái *queued* — chạy lại hoặc hủy sáng hôm sau. Chi tiết vận hành: `deploy/README.md`.

## Secrets và variables dùng bởi workflow

| Loại | Tên | Workflow |
| --- | --- | --- |
| Secret | `DEPLOY_HOST`, `SSH_KEY`, `DEPLOY_USER` | release |
| Secret | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `UPTIME_KUMA_PUSH_URL` | release, gate |
| Secret | `GITLEAKS_LICENSE` (chỉ khi repo thuộc organization) | check |
| Variable | `APP_DOMAIN` (bắt buộc để smoke test), `DEPLOY_DIR`, `DEPLOY_SSH_PORT`, `DEPLOY_PROFILE` | release |

Không có secret nào tên `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` trong CI: `check.yml` là cổng tất định (D13); prompt log và phiên Claude Code chạy trên máy dev, không trong Actions.
