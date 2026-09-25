---
name: epic
description: Chạy vòng lặp epic chuẩn của CTCV cho epic được chỉ định — plan mode với architect, thực thi song song, qa-tester, reviewer, security-redteam khi cần, PR có checklist ≤ 30 phút. Chỉ gọi tay bằng /epic.
argument-hint: "[E01..E12 | PILOT | DOSSIER]"
disable-model-invocation: true
effort: xhigh
---
Epic: $ARGUMENTS. Trạng thái hiện tại: !`cat docs/status/DAILY.md 2>/dev/null | head -40`

Mốc thực tế theo `docs/decisions/ADR-006` (không dùng lịch D1–D21 của plan §6). Kết quả `make check` gần nhất: `docs/status/last_check.json`.

1. **Plan mode.** Đọc `CLAUDE.md`, `epics/$ARGUMENTS.md`, các mục idea/plan/brief mà epic trỏ tới. Gọi `architect` với epic; nhận thiết kế + bảng việc + nội dung ADR (nếu có) + câu hỏi mở ≤ 3. Trình kế hoạch ≤ 40 dòng; **chờ người dùng duyệt** (và trả lời câu hỏi mở) trước khi rời plan mode. Chạm điểm dừng bắt buộc (đổi schema sau E05, thêm tool, đổi model, dữ liệu thật, > 20 giờ GPU / > 500.000 đ API, thư viện mới) → hỏi trước, không làm.
2. **Thực thi.** Giao việc độc lập cho `backend-dev` / `frontend-dev` / `data-engineer` / `ml-trainer` / `devops` theo kế hoạch, mỗi việc trên worktree riêng **khi repo đã có commit** (E01 chưa dùng worktree — giao theo thư mục sở hữu); tối đa 6 subagent đồng thời, không lồng quá 2 tầng; hợp nhất theo thứ tự backend → frontend → data; chạy `make check QUICK=1` sau mỗi lần hợp nhất. Orchestrator chỉ tự sửa thay đổi < 30 dòng.
3. **Cổng.** Gọi `qa-tester` (test + `make check`, cổng đồng bộ) rồi `reviewer` (DoD plan §14 + checklist bảo mật); nếu chạm `services/agent`, guardrail, tool, hook, permissions, `config/prompts` → gọi `security-redteam`. Đỏ → quay lại bước 2.
4. Tối đa **3 vòng sửa cho một lỗi**; quá 3 → báo người dùng kèm log 30 dòng cuối và 2 hướng xử lý.
5. **Đóng.** `docs-writer` cập nhật README mô-đun, CHANGELOG (`[Unreleased]` tiền tố `[$ARGUMENTS]`), ADR (từ nội dung architect), `docs/status/DAILY.md`; mở PR theo `.github/PULL_REQUEST_TEMPLATE.md` (làm gì · test thế nào · checklist ≤ 30 phút cho người dùng · rủi ro) trên nhánh `epic/$ARGUMENTS-<ten-ngan>` bằng `gh pr create`; **không chuyển epic khác** khi PR chưa merge.
6. **Kết thúc**: tóm tắt ≤ 15 dòng — đã làm, test (lệnh + kết quả), người dùng cần kiểm tra gì trong 30 phút, rủi ro/quyết định đang chờ.
