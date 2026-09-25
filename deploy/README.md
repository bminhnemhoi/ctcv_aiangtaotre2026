# deploy/ — triển khai và vận hành CTCV (tóm tắt runbook; bản đầy đủ: `docs/ops/RUNBOOK.md`)

Mọi thao tác đi qua `make` (Git Bash trên Windows, bash trên Linux). Không in giá trị biến môi trường ra màn hình (SEC-01); bí mật chỉ ở `.env` (gitignore) và GitHub Secrets.

```
deploy/
  docker-compose.yml        base: postgres 16, redis 7, qdrant 1.x, minio, api, agent, speech, vision, web,
                            caddy, uptime-kuma; profile cpu | gpu (vLLM upstream) | llama (llama.cpp)
  docker-compose.dev.yml    máy dev: bind mount + hot reload, mở cổng, không caddy/uptime-kuma
  docker-compose.prod.yml   staging/prod: prometheus, alertmanager, grafana, dcgm; restart, giới hạn tài nguyên, xoay log
  docker-compose.ci.yml     CI: cache BuildKit (type=gha) cho build
  defaults.env              biến mặc định an toàn cho container (bị .env ở gốc repo ghi đè)
  docker/                   <svc>.Dockerfile (context = gốc repo, D14), serve.py (entrypoint), healthcheck.py
  caddy/                    Caddyfile (biên: HTTPS tự động, header bảo mật), Caddyfile.web (trong image web)
  monitoring/               prometheus.yml, alert-rules.yml, alertmanager.yml, grafana/, uptime-kuma/README.md
  models/                   README (cờ vLLM), vllm.env.example, adapters/ (LoRA), cache/ (GGUF, gitignore)
  scripts/                  deploy.sh rollback.sh failover.sh backup.sh restore-drill.sh smoke.sh lib.sh (--dry-run)
  status/                   README: trang trạng thái công khai
  tests/                    pytest: `uv run pytest deploy/tests` (compose config, dry-run mọi script, workflow)
```

## Ba môi trường (plan §8, brief D29)

| Môi trường | Máy | Lệnh | Profile / model | Domain |
| --- | --- | --- | --- | --- |
| **dev** | máy dev Windows 11 (Docker Desktop, không GPU) | `make dev` (= base + dev overlay, `COMPOSE_PROFILES=cpu`) | `cpu`: không có `models`; `VLLM_BASE_URL` trỏ máy GPU qua SSH tunnel/Tailscale **hoặc** llama.cpp (`--profile llama`, hoặc `llama-server` trên host → `host.docker.internal`) | `localhost:5173` (Vite), api `:8000` |
| **staging** | máy GPU thuê 24 GB (Ubuntu) | `make deploy ENV=staging` | `gpu`: vLLM `Qwen/Qwen3.5-9B` AWQ (`deploy/models/README.md`) | `staging.<domain>` — HTTPS Caddy (tiên quyết E04) |
| **prod** | máy GPU (theo lịch) + VPS CPU trong nước luôn bật + máy dự phòng | tự động khi tag `v*` (`.github/workflows/release.yml`) hoặc `make deploy ENV=prod` | `gpu` trên máy GPU; `cpu`+`llama` trên VPS | `app.<domain>`, `status.<domain>` |

**Một lệnh:** `cp .env.example .env` → `make doctor` → `make install` → `make dev`. Kiểm tra: `curl localhost:8000/health`, mở `http://localhost:5173`. Dừng: `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml down` (thêm `-v` để xóa dữ liệu).

Giới hạn ở E01: `services/agent` chưa có HTTP server (container `agent` thoát với thông báo của `serve.py` cho đến E05); `ctcv-api` chưa có driver PostgreSQL nên `defaults.env` đặt `DATABASE_URL` SQLite trong volume `api_data` (E02 chuyển sang `postgresql+psycopg://…`, D15).

## Biến môi trường và bí mật

| Ở đâu | Biến | Dùng bởi |
| --- | --- | --- |
| `.env` gốc repo (máy dev / máy chủ, `DEPLOY_DIR/.env`) | mọi biến của `.env.example`: `APP_DOMAIN`, `STATUS_DOMAIN`, `ACME_EMAIL`, `POSTGRES_*`, `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, `MINIO_*`, `JWT_SECRET`, `VLLM_BASE_URL`, `PLANNER_MODEL`, `VLM_MODEL`, `ASR_MODEL`, `TTS_*`, `HF_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GRAFANA_ADMIN_PASSWORD`, `COMPOSE_PROFILES`, `TAG`, `REGISTRY` | container (qua `env_file`), Caddy, Grafana, Alertmanager |
| `.env` máy chạy script | `DEPLOY_HOST` (hoặc `DEPLOY_HOST_STAGING`/`_PROD`), `DEPLOY_USER`, `DEPLOY_DIR`, `DEPLOY_SSH_PORT`, `SSH_KEY_FILE`, `DEPLOY_PROFILE`, `UPTIME_KUMA_PUSH_URL`, `SMOKE_BASE_URL`, `PRIMARY_IP`, `BACKUP_IP`, `CF_API_TOKEN`, `CF_ZONE_ID`, `CF_RECORD_ID`, `CF_RECORD_ID_STATUS`, `DNS_PROVIDER`, `BACKUP_DIR`, `BACKUP_REMOTE`, `GPU_SSH_HOST` | `deploy/scripts/*.sh`, `make doctor GPU=1` |
| GitHub **Secrets** | `DEPLOY_HOST`, `SSH_KEY` (private key ed25519 của user deploy), `DEPLOY_USER`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `UPTIME_KUMA_PUSH_URL`, (`GITLEAKS_LICENSE` nếu repo thuộc organization) | `release.yml`, `gate.yml`, `check.yml` |
| GitHub **Variables** | `APP_DOMAIN` (bắt buộc cho smoke test), `DEPLOY_DIR` (mặc định `/opt/ctcv`), `DEPLOY_SSH_PORT`, `DEPLOY_PROFILE` (`gpu`/`cpu`) | `release.yml` |
| `deploy/models/vllm.env` (máy GPU) | `VLLM_*`, `LLAMA_*` | service `models`, `models-cpu` |

Thiếu `DEPLOY_HOST`/`SSH_KEY` → `release.yml` vẫn build và đẩy image lên GHCR nhưng **bỏ qua** bước deploy (có thông báo trong log).

## Quy trình deploy (plan §8) — `deploy/scripts/deploy.sh <staging|prod>`

1. `make check` đầy đủ (bỏ khi CI đã chạy: `--skip-check`).
2. Build image có nhãn `TAG` từ `deploy/docker/*.Dockerfile` (context gốc repo) và đẩy lên `REGISTRY` (`--no-build` khi CI đã đẩy). Image tên `ghcr.io/<owner>/ctcv-{api,agent,speech,vision,web}:<tag>`; `models` không build (vLLM upstream).
3. `rsync deploy/ → DEPLOY_HOST:DEPLOY_DIR/deploy/`, ghi `TAG=` vào `.env` máy chủ, `docker compose --env-file .env -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml --profile <gpu|cpu> pull && up -d --remove-orphans`.
4. `docker compose exec api alembic upgrade head` (migration tiến; rollback không hạ schema trừ khi `--db-downgrade`).
5. Smoke test `deploy/scripts/smoke.sh https://<APP_DOMAIN>`: lặp `/v1/health` tới khi 200 (24 lần × 5 s) rồi `/v1/scenarios` phải có đủ id trong `sandbox/scenarios/*.json` (E01: 1, E02: 4, E10: 12).
6. Cập nhật status page (monitor Push) → thông báo Telegram. Smoke đỏ + `--auto-rollback` → tự `rollback.sh` về tag trước.

Máy chủ lần đầu (RUNBOOK §1): Docker 27 + Compose v2 (+ NVIDIA container toolkit trên máy GPU), user `deploy` trong nhóm `docker`, `mkdir -p /opt/ctcv && cp .env.example /opt/ctcv/.env` rồi điền giá trị thật, `docker login ghcr.io` bằng PAT `read:packages` (hoặc để package công khai), mở cổng 80/443, `cp deploy/models/vllm.env.example deploy/models/vllm.env` trên máy GPU.

## Quay lui · chuyển máy · sao lưu · diễn tập

| Lệnh | Script | Mục tiêu |
| --- | --- | --- |
| `make rollback TAG=v1.0` | `rollback.sh` | pull tag cũ + `up -d --no-deps` các app service, smoke test, Telegram — **≤ 2 phút** (script tự đo và cảnh báo) |
| `make failover` | `failover.sh --to backup\|primary` | kiểm `/health` máy đích trực tiếp (`curl --resolve`) → đổi bản ghi A qua Cloudflare API với `proxied:false` (DNS-only) hoặc `DNS_PROVIDER=manual` → chờ DNS → smoke qua domain — **≤ 5 phút**; diễn tập ở T-60h |
| `make backup` | `backup.sh` (cron `0 */6 * * *` trên máy chủ) | `pg_dump -Fc` mỗi lần chạy (6 giờ) + snapshot Qdrant mỗi ngày → `BACKUP_DIR` (+ `rclone` sang `BACKUP_REMOTE` — object storage **trong nước**) — giữ **14 bản** (ADR-005); không backup ảnh màn hình (TTL 60 s) |
| `make restore-drill` | `restore-drill.sh` | khôi phục dump mới nhất vào project compose tạm `ctcv-restore-<ts>`, đếm `sessions`, so với bản sống, `down -v` — chạy trước T-72h |

Mọi script nhận `--dry-run` (chỉ in `[dry-run] <lệnh>`, không đụng máy chủ, không in token) — đây là cách `deploy/tests` kiểm chúng trên máy dev.

## CI/CD (`.github/workflows/`)

| Workflow | Khi nào | Ở đâu | Làm gì |
| --- | --- | --- | --- |
| `check.yml` | mọi PR, push `main` | GitHub-hosted | `make check QUICK=1`, `make e2e E2E=1`, `docker compose --profile cpu build`, gitleaks + `make audit`, `uv run pytest deploy/tests`. **Không bao giờ gọi model** (D13) |
| `gate.yml` | 02:00 giờ Việt Nam hằng đêm, tay, PR gắn nhãn `needs-gpu` | runner **self-hosted** trên máy GPU | `make gate` (eval QUICK=1 + red-team có model + load test); tải báo cáo lên artifact; không commit |
| `release.yml` | tag `v*` | GitHub-hosted | `check` → build + push GHCR → `deploy.sh` (tag có `-` → staging, còn lại → prod) → GitHub Release |

### Runner GPU tự host (cho `gate.yml`)

Trên máy GPU thuê (đã có Docker + NVIDIA toolkit + uv + pnpm + make + k6):

1. GitHub → *Settings → Actions → Runners → New self-hosted runner* → Linux x64; chạy đúng các lệnh tải/`config.sh` GitHub in ra, với: `--name gpu-01 --labels self-hosted,gpu --unattended --work /opt/ctcv-runner` (nhãn `gpu` **bắt buộc** — `runs-on: [self-hosted, gpu]`).
2. `sudo ./svc.sh install deploy && sudo ./svc.sh start` (chạy như user `deploy`, cùng nhóm `docker`).
3. Repo *Settings → Actions → General*: chỉ cho phép workflow của repo này dùng runner; **không** dùng runner này cho PR từ fork (mặc định GitHub đã tắt cho fork trên self-hosted).
4. Đặt secret `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` để gate đỏ báo về Telegram; `.env` của máy có `VLLM_BASE_URL=http://localhost:8040/v1` khi stack staging chạy cùng máy.
5. Thử: *Actions → gate → Run workflow*. Kiểm tra `nvidia-smi` xuất hiện trong log bước đầu.

Runner tắt cùng máy GPU (bật theo lịch để tiết kiệm — RUNBOOK §7): lịch đêm bỏ lỡ chỉ tạo run "queued"; hủy hoặc chạy lại sáng hôm sau.

## Checklist đóng băng 48 giờ trước chấm (plan §8)

- [ ] **T-72h**: `git tag v2.0` (bản chung kết) → `release.yml` xanh; `make gate` + `make release-check` đầy đủ, kết quả vào hồ sơ; `make restore-drill` ĐẠT.
- [ ] **T-60h**: bật máy dự phòng cùng image (`TAG` giống) + dữ liệu (restore từ backup mới nhất); `make failover` sang dự phòng rồi `make failover --to primary`; cả hai lần smoke xanh, ≤ 5 phút; ghi thời gian vào `docs/ops/incidents.md`.
- [ ] **T-48h**: khóa nhánh `main` (branch protection), tắt `release.yml` (*Actions → release → Disable workflow*), tắt cron backup? **Không** — backup vẫn chạy; dashboard chỉ đọc nếu cần; `docs/status/DAILY.md` ghi "FREEZE".
- [ ] **Trong 48 giờ**: 3 người × ca 8 giờ; mỗi ca xem status page + Grafana 2 lần; mọi sự cố → `/incident`, `docs/ops/incidents.md`, incident trên status page; không "sửa nhanh" ngoài quy trình rollback.
- [ ] **Sau chấm**: mở khóa, bật lại workflow, ghi bài học vào RUNBOOK.

## Ghi chú bắt buộc

- **ETH-12 / Cloudflare DNS-only**: nếu hồ sơ giữ cam kết "máy chủ trong nước", bản ghi DNS trên Cloudflare phải ở chế độ **DNS-only (đám mây xám)** — proxy cam kết thúc TLS ở biên Cloudflare ngoài nước. Caddy tự cấp chứng chỉ; chống DDoS bằng firewall máy + rate limit trong API (E11). `failover.sh` luôn ghi `proxied:false`.
- Ảnh màn hình sống 60 s trong MinIO (ADR-005): không backup, không log.
- `docker system prune` và `rm -rf` bị hook chặn trên máy dev; trên máy chủ chỉ dọn bằng `docker image prune --filter until=168h` sau khi rollback đã được xác nhận.
