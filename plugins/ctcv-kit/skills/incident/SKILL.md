---
name: incident
description: Xử lý sự cố vận hành hoặc trong 48 giờ đóng băng của CTCV — thu thập log/metrics, xác định phạm vi và mức P1–P3, áp runbook plan §8 (restart, rollback, failover), ghi docs/ops/incidents.md, đề xuất phòng ngừa. Chỉ gọi tay bằng /incident.
argument-hint: "[P1|P2|P3] <mô tả ngắn>"
disable-model-invocation: true
---
Sự cố: $ARGUMENTS. Mức: P1 (URL chết / rò rỉ dữ liệu / vi phạm bất biến), P2 (một dịch vụ lỗi, có fallback), P3 (suy giảm chất lượng). Không đoán: mỗi kết luận kèm bằng chứng (log, số).
1. **Thu thập** (subagent `devops` hoặc chỉ đọc): `/health` các dịch vụ, Uptime Kuma, Grafana (p95, VRAM, hàng đợi vLLM, 5xx, tỷ lệ escalate), `docker compose ps/logs --tail 200` (không `docker compose config` thiếu `--no-interpolate`), `docs/status/errors.log`, `docs/ops/incidents.md` (sự cố tương tự).
2. **Phạm vi**: dịch vụ, số người dùng ảnh hưởng, có lộ dữ liệu không (mặc định: hệ thống không lưu PII; nếu nghi rò rỉ → P1, dừng dịch vụ liên quan, báo người dùng ngay).
3. **Áp runbook** `docs/ops/RUNBOOK.md` / plan §8: vLLM treo/OOM → watchdog restart, lặp 3 lần → giảm max batch trong config (qua ADR nếu ngoài đóng băng); GPU chính chết → `make failover` ≤ 5 phút; ASR lỗi → bật bàn phím chữ to, restart speech; tấn công/quét → rate limit, Cloudflare rule, kiểm không rò rỉ; bản lỗi → `make rollback TAG=` ≤ 2 phút. Trong **48 giờ đóng băng**: không deploy ngoài quy trình, mọi thay đổi phải có mục sự cố và người trực ca xác nhận.
4. **Ghi** `docs/ops/incidents.md` theo mẫu `INC-YYYYMMDD-NN` (phát hiện, phạm vi, dòng thời gian, nguyên nhân gốc, hành động, khắc phục xong, phòng ngừa, liên quan) và bảng tóm tắt; cập nhật status page nếu người dùng bị ảnh hưởng.
5. **Phòng ngừa**: test hồi quy / kịch bản red-team / cảnh báo mới; đề xuất ADR nếu đổi kiến trúc; việc chưa làm → BACKLOG.
Kết thúc ≤ 10 dòng: mức, nguyên nhân gốc, thời gian khắc phục, việc còn lại, ai cần làm gì (trực ca / người dùng). Ba nguyên tắc bất biến không được tạm bỏ vì sự cố.
