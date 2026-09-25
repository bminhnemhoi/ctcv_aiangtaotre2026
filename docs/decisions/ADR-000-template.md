# ADR-NNN — <Tên quyết định ngắn>

Ngày: YYYY-MM-DD · Người quyết: <tên/vai> · Trạng thái: **đề xuất** | **chốt** | **thay thế bởi ADR-MMM** | **hủy** · Liên quan: <epic, phát hiện id, D-số trong E01-brief>

## Bối cảnh
Vấn đề phải quyết là gì, ràng buộc nào (thời gian, giấy phép, phần cứng, BTC), phương án nào đã cân nhắc (2–4 dòng, dẫn nguồn: idea/plan/prompt §, phát hiện trong `docs/analysis/`).

## Lựa chọn
Quyết định một câu, rồi các điểm cụ thể đo được (tên model, ngưỡng, đường dẫn file, target Makefile). Nêu phương án B nếu điều kiện chốt không đạt.

## Hệ quả
- Được gì / mất gì; ảnh hưởng tới epic nào, file cấu hình nào (`config/*.yaml`), test nào.
- Việc phải làm ngay (ai, hạn) và rủi ro còn lại.

## Trạng thái
Lịch sử: YYYY-MM-DD đề xuất → YYYY-MM-DD chốt tại PR #… (ai) → … Điều kiện để xem lại (ví dụ: eval dưới ngưỡng chặn 2 lần, BTC đổi thể lệ).

---
Quy ước: ≤ 1 trang; tiếng Việt (thuật ngữ giữ tiếng Anh); ADR không bị sửa sau khi "chốt" — thay đổi → ADR mới ghi "thay thế"; mọi ADR phải được tham chiếu từ epic hoặc CLAUDE.md; đổi model, schema DB sau E05, tool agent, hook/settings luôn cần ADR (plan §6, §11).
