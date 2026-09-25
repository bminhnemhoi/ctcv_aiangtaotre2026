---
name: review
description: Xử lý góp ý của người dùng trên PR sau khi họ test — xác nhận hiểu, sửa, test hồi quy, make check, reviewer và security-redteam rà lại theo DoD; bảng góp ý → thay đổi → test. Chỉ gọi tay bằng /review.
argument-hint: "[E01..E12 | số PR]"
disable-model-invocation: true
---
Tôi đã test PR $ARGUMENTS; góp ý nằm trong bình luận PR — đọc bằng `gh pr view $ARGUMENTS --comments` và `gh api repos/{owner}/{repo}/pulls/<số>/comments` (không dùng MCP github — D24). Với mỗi góp ý: (1) diễn đạt lại để xác nhận hiểu đúng, (2) sửa (giao subagent đúng thư mục nếu > 30 dòng), (3) thêm test hồi quy, (4) chạy `make check QUICK=1`. Sau đó gọi `reviewer` review lại toàn bộ PR theo Definition of Done (plan §14, CLAUDE.md) và checklist bảo mật OWASP Agentic trong CLAUDE.md; gọi `security-redteam` nếu PR chạm `services/agent`, guardrail, tool, hook, permissions hoặc `config/prompts`. Không xóa/skip test, không nới ngưỡng eval, không đổi cấu hình bảo mật để cho xanh; tối đa 3 vòng cho một góp ý rồi báo lại kèm log và 2 hướng. Cập nhật CHANGELOG/README nếu thay đổi hành vi; đẩy lên nhánh `epic/…` bằng `git push origin epic/…` (không force). Kết thúc bằng bảng: góp ý → thay đổi (file) → test (tên); liệt kê điểm bạn tự phát hiện thêm và điểm cần người dùng quyết.
