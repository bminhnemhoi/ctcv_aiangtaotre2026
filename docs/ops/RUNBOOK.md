# RUNBOOK — Triển khai và vận hành CTCV (plan §8 thành lệnh; đường dẫn theo brief §1)

Mọi thao tác đi qua `make` (Makefile brief §10); script hiện thực nằm ở `deploy/scripts/*.sh` (gói I, E12). Máy dev Windows chạy `make` trong Git Bash; lệnh trên máy chủ chạy qua SSH. Không in giá trị biến môi trường ra màn hình (SEC-01) — chỉ tên biến.

## 0. Môi trường
| Môi trường | Máy | Compose | Model | Domain |
| --- | --- | --- | --- | --- |
| dev | máy dev Windows 11 (Docker Desktop, không GPU) | `deploy/docker-compose.yml` + `docker-compose.dev.yml`, profile `cpu` | `planner_small` Qwen3.5-2B GGUF (llama.cpp) hoặc `VLLM_BASE_URL` trỏ máy GPU qua SSH tunnel/Tailscale | localhost |
| staging | máy GPU thuê (Ubuntu 22.04, 24 GB) | `docker-compose.prod.yml`, profile `gpu` | vLLM Qwen3.5-9B AWQ (+ LoRA sau E07) | `staging.<domain>` (hoặc `cloudflared` tạm) |
| prod | VPS CPU trong nước (luôn bật) + máy GPU theo lịch + máy dự phòng | profile `cpu` (VPS) + `gpu` (máy GPU) | fallback tự động CPU ↔ GPU theo health | `app.<domain>`, `status.<domain>` |

Biến bắt buộc (`.env`, không commit): xem `.env.example`; kiểm bằng `make doctor` (dev) / `make doctor GPU=1` (máy thuê: SSH, `nvidia-smi`, vLLM `/v1/models`).

## 1. Dựng staging lần đầu (E12-lite, 21–22/9 — tiên quyết E04)
1. Máy GPU: cài Docker 27 + Compose v2 + NVIDIA runtime; tạo user deploy, SSH key; mở 80/443.
2. Máy dev: `make doctor GPU=1` (SSH tới máy thuê) → xanh.
3. `make build` (image có hash; `models` không build — pull image vLLM upstream).
4. `make deploy ENV=staging` → `deploy/scripts/deploy.sh`: đẩy image lên registry riêng → SSH → `docker compose --profile gpu pull && up -d` → Alembic upgrade → `deploy/scripts/smoke.sh` (6/12 kịch bản qua API) → cập nhật status page → thông báo Telegram.
5. Caddy (`deploy/caddy/Caddyfile`) cấp HTTPS tự động; nếu chưa có domain: `cloudflared tunnel` tạm (ghi trong `docs/status/DAILY.md`).
6. Uptime Kuma (`deploy/status/`): monitor `/health` của api, speech, vision, models mỗi 30 s; web mỗi 60 s; status page công khai hiển thị chế độ GPU/CPU; giữ xanh ≥ 24 giờ trước ngày nộp.

## 2. Deploy thường (tự động khi tag `v*`, `.github/workflows/release.yml`)
`git tag v1.0 && git push origin v1.0` → CI: build image có hash → `make check` đầy đủ → push registry → `make deploy ENV=prod` → smoke test → status → Telegram. Deploy tay (chỉ ngoài thời gian đóng băng): `make deploy ENV=prod`.

## 3. Rollback / failover / backup
- `make rollback TAG=<tag trước>` (`deploy/scripts/rollback.sh`): compose pull tag cũ + up -d + Alembic downgrade nếu migration có `down`; mục tiêu ≤ 2 phút.
- `make failover` (`deploy/scripts/failover.sh`): chuyển DNS (Cloudflare DNS-only API) sang máy dự phòng cùng image + dữ liệu; mục tiêu ≤ 5 phút; diễn tập trước T-60h.
- `make backup` (`deploy/scripts/backup.sh`, cron): PostgreSQL dump mỗi 6 giờ, Qdrant snapshot hằng ngày → object storage khác máy (trong nước), giữ 14 bản; **không** backup ảnh (TTL 60 s), không chép dữ liệu pilot ra ngoài.
- `make restore-drill` (`deploy/scripts/restore_drill.sh`): khôi phục dump mới nhất vào Postgres tạm, so số dòng; chạy trước T-72h (không hằng tuần — F13).

## 4. Giám sát và ngưỡng cảnh báo (Telegram)
| Chỉ báo | Ngưỡng | Nguồn |
| --- | --- | --- |
| p95 hỏi đáp | > 3 s trong 5 phút (mục tiêu < 4 s; sandbox < 1 s; TTFA < 1,5 s) | script p95 từ log JSON, `/metrics` |
| Lỗi 5xx | > 2 % | api log |
| VRAM | > 92 % | `nvidia-smi` / vLLM `/metrics` |
| Dịch vụ down | 2 lần liên tiếp | Uptime Kuma |
| Tỷ lệ escalate | tăng bất thường (> 2× trung bình ngày) | api log |
| Rate limit | kích hoạt hàng loạt từ 1 IP | api log |
| Chi phí GPU | > 80 % hạn mức 300 giờ | `training/budget.json`, hóa đơn |
Prometheus/Grafana: chỉ khi còn thời gian (BACKLOG, F13).

## 5. Đóng băng trước chấm (v1.0 bản nộp: nhẹ; v2.0 chung kết: đầy đủ — BTC chỉ đòi 48 giờ ở chung kết)
| Mốc | Ngày (chung kết) | Việc | Lệnh |
| --- | --- | --- | --- |
| T-72h | 17/11 (T3) | tag bản cuối, eval đầy đủ + load test, ghi kết quả vào hồ sơ; `make restore-drill` | `git tag v2.0`, `make gate`, `make release-check` |
| T-60h | 18/11 | bật máy dự phòng cùng image + dữ liệu; diễn tập chuyển DNS | `make failover` (rồi chuyển lại) |
| T-48h | 19/11 (T5) | khóa nhánh `main` (branch protection), tắt deploy tự động, dashboard chỉ đọc nếu cần | GitHub settings; `docs/status/DAILY.md` ghi "FREEZE" |
| Trong 48 giờ | 20–22/11 | trực luân phiên 3 người × ca 8 giờ; mỗi ca xem status/p95 2 lần; mọi sự cố ghi `docs/ops/incidents.md`; không "sửa nhanh" ngoài quy trình | `/incident` |
| Sau chấm | 23/11 | mở khóa, ghi bài học | — |
Bản nộp 29/9: status page xanh ≥ 24 giờ trước nộp; không cần khóa main nhưng không deploy trong ngày nộp.

## 6. Bảng sự cố
| Sự cố | Dấu hiệu | Hành động | Ai |
| --- | --- | --- | --- |
| vLLM treo/OOM | p95 tăng, VRAM 100 % | watchdog tự restart container; lặp 3 lần → giảm `max_num_seqs` trong compose; agent tự fallback `planner_small` (status page hiện "CPU") | tự động → trực ca |
| GPU máy chính chết | health đỏ 2 lần | `make failover` (≤ 5 phút); nếu máy dự phòng không có GPU → chế độ CPU toàn phần | trực ca |
| ASR lỗi | escalate tăng, `/v1/speech/asr` 5xx | bật bàn phím chữ to (UI tự động khi lỗi), `docker compose restart speech` | tự động + trực ca |
| Crawler/RAG lỗi thời | hash nguồn đổi (`manifest.jsonl`) | không cập nhật trong đóng băng; ghi việc | sau chấm |
| Tấn công/quét | rate limit kích hoạt, log lạ | chặn IP ở Caddy/Cloudflare rule (DNS-only: dùng firewall máy), kiểm tra không rò rỉ (log không PII) | trực ca |
| Prompt log lệch hash | `make docs-check`/`promptlog-export` đỏ | KHÔNG sửa file; ghi incident; giữ nguyên, giải trình trong README Drive | trực ca + người dùng |
| Hết ngân sách GPU | budget > 80 % | tắt GPU ngoài giờ pilot/chấm; giảm epoch; dùng model nhỏ hơn cho sinh dữ liệu | người dùng |

## 7. Chi phí
GPU bật theo lịch (tắt đêm ngoài pilot/chấm); Pha A ≤ 60–80 giờ; tổng 300 giờ (5–8 triệu đồng); VPS + domain ≤ 1 triệu; API sinh dữ liệu ≤ 2 triệu (hook `budget.py` chặn > 500.000 đ/tác vụ). Ghi lũy kế vào `docs/status/DAILY.md` mỗi ngày.
