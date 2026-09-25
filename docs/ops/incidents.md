# incidents — Nhật ký sự cố vận hành (ghi bởi `/incident` hoặc người trực ca; không xóa dòng cũ)

Quy ước: một mục mỗi sự cố, mới nhất ở trên; thời gian UTC+7; mức: P1 (URL chết / rò rỉ dữ liệu), P2 (một dịch vụ lỗi, có fallback), P3 (suy giảm chất lượng). Trong 48 giờ đóng băng, mọi thay đổi đều phải có mục ở đây và không được deploy ngoài quy trình (RUNBOOK §5).

## Bảng tóm tắt
| # | Thời điểm | Mức | Dịch vụ | Dấu hiệu | Hành động | Thời gian khắc phục | Phòng ngừa | Người |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Mẫu một mục
```
## INC-YYYYMMDD-NN — <tên ngắn> (P1|P2|P3)
- Phát hiện: <thời điểm>, bởi <ai/monitor>, dấu hiệu: <p95/health/log>
- Phạm vi: <dịch vụ, số người dùng ảnh hưởng, dữ liệu có bị lộ không (mặc định: không PII trong hệ thống)>
- Dòng thời gian: HH:MM … → HH:MM …
- Nguyên nhân gốc:
- Hành động: <lệnh make/script đã chạy, rollback/failover?>
- Khắc phục xong: <thời điểm>, tổng <phút>
- Phòng ngừa: <test hồi quy, thay đổi cấu hình, ADR nếu cần>
- Liên quan: <PR, DAILY ngày, ADR>
```

## Sự cố
- (chưa có)
