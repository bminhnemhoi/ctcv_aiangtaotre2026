# Uptime Kuma — giám sát và cảnh báo (plan §8)

Uptime Kuma chạy trong service `uptime-kuma` (`deploy/docker-compose.yml`), dữ liệu ở volume `uptime_kuma_data`, được Caddy đưa ra `https://<STATUS_DOMAIN>` (`deploy/caddy/Caddyfile`). Trang trạng thái công khai cho giám khảo: xem `deploy/status/README.md`. Prometheus/Grafana/Alertmanager (overlay prod) bổ sung số liệu p95/GPU; Uptime Kuma là lớp giám sát **tối thiểu bắt buộc** (E11, F13).

## Lần đầu

1. Mở `https://<STATUS_DOMAIN>` → tạo tài khoản quản trị (mật khẩu vào trình quản lý mật khẩu của đội, **không** vào repo).
2. *Settings → Notifications → Setup Notification → Telegram*: `Bot Token` = `TELEGRAM_BOT_TOKEN`, `Chat ID` = `TELEGRAM_CHAT_ID` (cùng bot với `deploy/scripts/lib.sh`), bật *Default enabled* và *Apply on all existing monitors*.
3. *Settings → General*: múi giờ `Asia/Ho_Chi_Minh`; *Primary Base URL* = `https://<STATUS_DOMAIN>`.
4. Tạo các monitor theo bảng dưới (thứ tự = thứ tự hiện trên status page).

## Monitor (health check mỗi 30 s — idea §10; "down 2 lần liên tiếp" = Retries 1)

Các dịch vụ chỉ nghe trên mạng compose; Uptime Kuma nằm cùng mạng nên gọi thẳng tên service.

| Tên | Loại | URL / Host | Interval | Retries | Retry interval | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| `api /health` | HTTP(s) – Keyword | `http://api:8000/health` — keyword `"status"` | 30 s | 1 | 30 s | Cả checks `db/redis/qdrant`; keyword `"error"` (đảo, *Invert keyword*) để bắt phụ thuộc lỗi |
| `speech /health` | HTTP(s) | `http://speech:8020/health` | 30 s | 1 | 30 s | |
| `vision /health` | HTTP(s) | `http://vision:8030/health` | 30 s | 1 | 30 s | |
| `models vLLM` | HTTP(s) | `http://models:8040/health` | 30 s | 1 | 30 s | Chỉ máy GPU (profile `gpu`). Trên VPS CPU: `http://models-cpu:8040/health` (profile `llama`) |
| `agent /health` | HTTP(s) | `http://agent:8010/health` | 30 s | 1 | 30 s | Thêm khi `services/agent` có HTTP server (E05) |
| `web (công khai)` | HTTP(s) – Keyword | `https://<APP_DOMAIN>/` — keyword `Cầm Tay Chỉ Việc` | 60 s | 1 | 30 s | Đi qua Caddy + DNS thật, đúng đường người dân dùng |
| `web /healthz` | HTTP(s) | `http://web:80/healthz` | 60 s | 1 | 30 s | Container static (Caddy trong image web) |
| `chế độ đang chạy` | HTTP(s) – Json Query | `http://api:8000/health` — `$.checks.planner` = `gpu` | 60 s | 0 | — | E11 (CF-07): status page hiện "GPU nhanh" / "CPU dự phòng"; mô tả monitor ghi rõ ý nghĩa. Tạo khi `/health` có trường này |
| `deploy push` | Push | (Uptime Kuma sinh URL) | 24 h | 0 | — | `deploy.sh` gọi `UPTIME_KUMA_PUSH_URL?status=up&msg=deploy+<tag>` sau smoke test → đánh dấu mốc deploy trên timeline |
| `postgres` | TCP Port | `postgres:5432` | 60 s | 1 | 30 s | |
| `redis` | TCP Port | `redis:6379` | 60 s | 1 | 30 s | |
| `qdrant` | HTTP(s) | `http://qdrant:6333/healthz` | 60 s | 1 | 30 s | |
| `chứng chỉ TLS` | HTTP(s) | `https://<APP_DOMAIN>/` — *Certificate Expiry Notification* bật | 24 h | 0 | — | Caddy tự gia hạn; cảnh báo 14/7 ngày là lưới an toàn |

Ngưỡng cảnh báo còn lại của plan §8 (p95 > 3 s/5 phút, 5xx > 2 %, VRAM > 92 %) thuộc Prometheus + `alert-rules.yml` → Alertmanager → Telegram (overlay prod); Uptime Kuma chỉ phụ trách "dịch vụ down 2 lần liên tiếp" và uptime công khai.

## Vận hành

- Bảo trì có kế hoạch (deploy ngoài đóng băng): *Maintenance → Schedule* để status page không tính downtime.
- Sao lưu cấu hình: volume `uptime_kuma_data` nằm trong `backup.sh`? **Không** — chỉ Postgres + Qdrant được backup (plan §8). Xuất tay *Settings → Backup* sau khi cấu hình xong và lưu cùng bí mật của đội.
- Không mở cổng 3001 ra ngoài; chỉ đi qua Caddy (`STATUS_DOMAIN`). Trang admin cần đăng nhập; status page là công khai.
- Trước ngày nộp: status page xanh liên tục ≥ 24 giờ (plan §15 checklist); ảnh chụp uptime vào `docs/screens/<ngày>/` bằng `make evidence`.
