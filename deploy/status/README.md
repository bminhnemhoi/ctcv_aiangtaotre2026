# deploy/status — trang trạng thái công khai (plan §8, idea §10, E11)

Giám khảo và Tỉnh đoàn tự xem hệ thống sống hay không tại `https://<STATUS_DOMAIN>` (Uptime Kuma, service `uptime-kuma`). URL này ghi vào hồ sơ mục 10 và README gốc. Cấu hình monitor và cảnh báo: `deploy/monitoring/uptime-kuma/README.md`.

## Tạo status page (5 phút, một lần)

1. Đăng nhập Uptime Kuma → *Status Pages → New Status Page*: tên `Cầm Tay Chỉ Việc — trạng thái dịch vụ`, slug `ctcv` → URL `https://<STATUS_DOMAIN>/status/ctcv`.
2. *Description* (chữ to, tiếng Việt): "Ứng dụng mô phỏng — trang này cho biết dịch vụ đang chạy. Nếu có sự cố, đội trực sẽ cập nhật ở đây."
3. Thêm nhóm và monitor theo thứ tự:
   - **Người dân dùng được không?** — `web (công khai)`, `api /health`.
   - **Trí tuệ nhân tạo** — `models vLLM` (hoặc `models-cpu`), `chế độ đang chạy` (GPU nhanh / CPU dự phòng — CF-07), `speech /health`, `vision /health`.
   - **Hạ tầng** — `postgres`, `redis`, `qdrant`, `chứng chỉ TLS`.
4. Bật *Show Powered By* = tắt, *Show Certificate Expiry* = bật, *Google Analytics* = trống (không theo dõi người xem).
5. *Custom CSS* (tùy chọn, chữ ≥ 20 pt cho người lớn tuổi):

   ```css
   body { font-size: 1.35rem; }
   .title { font-size: 2rem; }
   ```

6. *Save* → mở URL ở chế độ ẩn danh để chắc chắn xem được **không cần đăng nhập**; Caddy trỏ gốc `STATUS_DOMAIN` sang Uptime Kuma nên `https://<STATUS_DOMAIN>/` cũng có thể đặt làm *Default status page* (*Settings → Status Page*).

## Thông báo sự cố trên trang

Trong đóng băng 48 giờ (plan §8), ca trực đăng *Incident* ngay trên status page (nút *Create Incident*, mức `Info/Warning/Danger`, tiếng Việt, ≤ 2 câu) đồng thời ghi `docs/ops/incidents.md`. Khi failover sang máy dự phòng, `deploy/scripts/failover.sh` đã đổi DNS cho cả `STATUS_DOMAIN` nếu có `CF_RECORD_ID_STATUS`, nên trang vẫn mở được.

## Mốc deploy

`deploy/scripts/deploy.sh` gọi monitor Push (`UPTIME_KUMA_PUSH_URL`) sau khi smoke test xanh; timeline của status page vì thế hiện mỗi lần lên bản mới kèm tag. Tạo monitor Push trước, dán URL vào `.env` trên máy chạy deploy (hoặc GitHub Secrets cho `release.yml`).

## Kiểm tra trước ngày nộp / chấm

- [ ] Trang mở được từ mạng di động, không đăng nhập, chữ đọc được trên điện thoại.
- [ ] Uptime 24 giờ gần nhất ≥ 99 % cho `web` và `api` (plan §15: xanh liên tục ≥ 24 giờ).
- [ ] Monitor `chế độ đang chạy` hiện đúng GPU/CPU sau khi diễn tập `make failover`.
- [ ] Ảnh chụp trang vào `docs/screens/<ngày>/` (`make evidence`) để đưa vào hồ sơ.
