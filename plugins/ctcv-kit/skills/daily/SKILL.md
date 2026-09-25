---
name: daily
description: Cập nhật docs/status/DAILY.md đầu ngày — KPI plan §11 (epic, % test xanh, eval quick, red-team, p95, chi phí, câu hỏi chờ, rủi ro), so tiến độ với ADR-006, báo cáo rà phạm vi ở mốc 22/9 và 25/9. Chỉ gọi tay bằng /daily.
argument-hint: "[YYYY-MM-DD | hôm nay]"
disable-model-invocation: true
---
# /daily $ARGUMENTS (prompt.md §6, plan P2, plan §11 KPI; mẫu ngày trong `docs/status/DAILY.md`)

Ngày: $ARGUMENTS (mặc định hôm nay). Không gọi model; mọi số phải có nguồn — không có thì ghi "chưa có".

1. Đọc `docs/status/DAILY.md` (mục ngày gần nhất + "Phiên gần nhất" do hook ghi — **không sửa mục đó**), `docs/status/last_check.json`, `docs/status/CHECKPOINT.md`, `docs/status/errors.log` (lỗi lặp), `docs/status/subagents.log`, `eval/reports/` (mới nhất), `training/budget.json` (`spent`), `docs/decisions/ADR-006` (bảng pha), `epics/E0X.md` đang làm (câu hỏi mở), `git status`/`git log -5`.
2. Thêm mục `## YYYY-MM-DD (Thứ …) — Pha … / mốc ADR-006: …` lên đầu (sau "Phiên gần nhất"), điền bảng KPI theo mẫu: Epic đang làm và % test xanh (nguồn last_check/pytest) · Số test / e2e · Eval quick gần nhất (hoặc "chưa có GPU") · Số lỗi red-team (`make redteam`) · Độ trễ p95 staging · Chi phí GPU/API lũy kế (`budget.json`) · Câu hỏi đang chờ người dùng (liệt kê) · Rủi ro mới.
3. So tiến độ với bảng pha ADR-006: sớm/trễ bao nhiêu ngày. Tại **22/9** (chưa có v0.1 = E02 xanh) và **25/9** (freeze scope, E05 chưa xanh) → lập báo cáo rà phạm vi theo ADR-006 mục 4 và đề xuất cắt (không tự cắt — người dùng quyết). Hackathon: `/daily` mỗi 4 giờ.
4. Ghi "Việc hôm nay (Claude)" và "Việc người dùng hôm nay" (từ brief §17.13, ADR-006 mục 6, epic đang làm); nhắc commit `docs/prompt-log/` cuối ngày (prompt-log README quy tắc 5) và `make promptlog-sync` nếu có phiên thiếu trong INDEX.
5. Nếu `docs/status/last_check.json` cũ hơn thay đổi mã (hook `daily` đã nhắc) → đề nghị chạy `make check QUICK=1` trước khi làm epic.
6. Kết thúc ≤ 10 dòng: KPI chính, sớm/trễ, 3 việc ưu tiên hôm nay, câu hỏi cần người dùng trả lời ngay.
