# 13. Lịch sử câu lệnh và hình ảnh minh chứng quá trình phát triển sản phẩm từ bản nháp đến khi hoàn thiện

> Nội dung trình bày: Đường liên kết đến thư mục Google Drive chứa lịch sử câu lệnh, hình ảnh minh chứng quá trình phát triển sản phẩm, tài liệu kỹ thuật, mã nguồn hoặc minh chứng liên quan; bắt buộc mở quyền truy cập trước khi nộp.

**Đường liên kết Google Drive (đã mở quyền "Bất kỳ ai có liên kết"):** {{team:drive_url}}

**Kho mã nguồn:** {{team:repo_url}} — tag bản nộp `{{team:repo_tag}}`, giấy phép Apache-2.0, README chạy một lệnh.

Thư mục Drive có cấu trúc cố định, được đồng bộ từ repo bằng `make promptlog-export` (kèm cổng kiểm tra bí mật/PII) và `make evidence`:

| Thư mục | Nội dung | Tính toàn vẹn |
| --- | --- | --- |
| `01-prompt-log/` | Toàn bộ phiên Claude Code: transcript `.jsonl` gốc theo `session_id` và bản Markdown dễ đọc; `INDEX.md` với SHA-256 và git HEAD của từng phiên; các phiên trước ngày 1 (soạn tài liệu ý tưởng/kế hoạch) xuất tay vào `pre-D1/` | Hash trong INDEX khớp file; lịch sử commit của `docs/prompt-log/` trên GitHub |
| `02-system-prompts/` | Snapshot "system prompt" theo phiên: `CLAUDE.md`, `.claude/agents/*.md`, `.claude/skills/**`, `settings.json`, `config/prompts/*` kèm hash; README giải thích các tầng system prompt (phần nội bộ của Claude Code do Anthropic quản lý, không xuất được) | Hash theo git |
| `03-subagent-transcripts/` | Transcript của các subagent | Hash |
| `04-minh-chung-theo-ngay/` | Ảnh chụp ứng dụng bằng Playwright mỗi ngày (`YYYY-MM-DD-E0X-*.png`) và snapshot `DAILY.md`: từ bản nháp đến bản nộp | Tên file theo ngày và epic |
| `05-tai-lieu-ky-thuat/` | ADR-001…006, README các dịch vụ, báo cáo eval (`eval/reports/`), báo cáo red-team, báo cáo thử nghiệm sơ bộ (ẩn danh) | — |
| `06-ma-nguon/` | Link repo và tag; bản ZIP mã nguồn tại tag | — |
| `07-prompt-cong-cu-khac/` | Prompt template và tham số của bước sinh dữ liệu tổng hợp và LLM-judge | — |

**Chính sách công bố:** Prompt Log không được sửa tay; nếu cổng export phát hiện bí mật hoặc dữ liệu cá nhân, chuỗi đó được thay bằng `[REDACTED-SECRET sha256:<8>]` và việc thay được ghi trong `INDEX.md` và README của Drive. Dữ liệu pilot thô và thông tin cá nhân của thành viên không có trên Drive.
