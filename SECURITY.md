# Chính sách bảo mật — Cầm Tay Chỉ Việc (CTCV)

## Báo cáo lỗ hổng

- Dùng **GitHub Security Advisory** của kho mã (tab *Security → Report a vulnerability*) để báo cáo riêng tư; không mở issue công khai cho lỗ hổng chưa vá.
- Nếu không dùng được Security Advisory, mở một GitHub Issue **không kèm chi tiết kỹ thuật**, chỉ đề nghị người duy trì mở kênh riêng. Kho mã không công bố e-mail hay số điện thoại cá nhân (quyết định D25).
- Cam kết: xác nhận trong 48 giờ, đánh giá mức độ trong 5 ngày, vá lỗi mức cao trước mọi lần phát hành/tag tiếp theo và ghi vào `docs/ops/incidents.md`.
- Không tấn công hệ thống staging/production đang phục vụ pilot với người thật; dùng môi trường dev hoặc kịch bản red-team mô tả dưới đây.

## Phạm vi

| Trong phạm vi | Ngoài phạm vi |
| --- | --- |
| PWA `apps/web`, API `services/api`, agent `services/agent`, speech/vision, sandbox, drills, script triển khai `deploy/` | Model gốc của bên thứ ba (Qwen, PhoWhisper, BGE…) — báo cho tác giả gốc |
| Prompt injection qua nội dung người dùng dán/chụp, rò rỉ OTP/mật khẩu, hành động thay người dùng, vượt guardrail, leo thang quyền giữa 3 vai (người dân / tình nguyện viên / cán bộ) | Lỗi của nhà cung cấp hạ tầng (Cloudflare, máy GPU thuê) |
| Rò rỉ PII trong log, ảnh màn hình, prompt log xuất bản, bản kê khai | Kịch bản cần truy cập vật lý vào máy chủ |

Bản prototype hiện tại (Data for Life 2026) phục vụ thật `/v1/coach/ask`, `/v1/coach/intake-check`, `/v1/auth/join` và `/v1/auth/login` (chế độ demo, tắt mặc định — khi tắt trả `501`), cùng `/v1/health`, `/v1/metrics`, `/v1/scenarios`; các route lớp học, phiên sandbox, drill, báo cáo, giọng nói và ảnh màn hình trả `501 Chưa hiện thực`. Demo cục bộ chỉ nghe `127.0.0.1`. Câu hỏi của người dùng không được lưu hay ghi log (`tests/invariants/test_api_ask_privacy.py`).

## Ba nguyên tắc bất biến (có test tự động, không được bỏ)

1. **Agent không có tool nào hành động trên hệ thống thật hay tài khoản thật.** Whitelist đóng gồm 8 tool trong `config/tools.yaml`, mỗi tool khai báo `side_effect ∈ {none, sandbox, log}`; test bất biến (`tests/invariants`) cấm module tool import `httpx`/`requests`/`subprocess`. Sandbox là ứng dụng mô phỏng tách biệt, luôn có nhãn "mô phỏng".
2. **Không lưu dữ liệu định danh.** Không cột CCCD/OTP/mật khẩu/số thẻ trong CSDL; `display_name` là biệt danh/mã do tình nguyện viên cấp; ảnh màn hình che PII trước khi vào model và xóa sau 60 giây (`config/app.yaml: screen_ttl_seconds`); log JSON đi qua `PiiScrubFilter` (`libs/core`, regex trong `config/guardrails.yaml`), giữ 30 ngày; câu hỏi/đáp chỉ lưu hash.
3. **Mọi dữ kiện đọc cho người dân phải có trích dẫn.** Không có nguồn từ kho hướng dẫn chính thống thì huấn luyện viên nói "không chắc" và escalate cho tình nguyện viên (`escalate_confidence` trong `config/guardrails.yaml`).

Kiến trúc hỗ trợ: planner tách khỏi **LLM cách ly** (ADR-004) — nội dung không tin cậy chỉ đi qua LLM cách ly và trả về schema kín, không bao giờ vào prompt của planner dưới dạng chuỗi tự do; JWT ngắn hạn, phân quyền 3 vai, rate limit theo thiết bị; secret chỉ trong `.env`/GitHub Secrets; gitleaks + pip-audit + allow-list thư viện chạy trong `make audit` và pre-commit.

## Chính sách red-team

- Bộ kịch bản tấn công tự động nằm ở `eval/redteam/scenarios.jsonl` — hiện 92 kịch bản, 92 đạt, 0 rò rỉ, 0 hành động thật (`eval/reports/latest.json` → `suites.redteam`; mục tiêu 200 kịch bản ở E11): prompt injection trực tiếp và qua nội dung dán vào, dụ hỏi OTP/mật khẩu, yêu cầu thao tác thay, rò rỉ system prompt, PII trong đầu ra, lạm dụng drill, tấn công nhiều bước.
- `make redteam` (guardrail thuần, không cần model) nằm trong `make check` — chạy **mỗi PR**; `make redteam-model` (có model) nằm trong `make gate` — chạy hằng đêm và trước mỗi tag. Ngưỡng: **0 rò rỉ, 0 hành động thay người dùng** (`config/eval.yaml: suites.redteam`); bất kỳ lỗi nào chặn phát hành, sửa guardrail rồi thêm test hồi quy.
- Mọi thay đổi guardrail hoặc prompt hệ thống (`config/guardrails.yaml`, `config/prompts/*`) phải kèm chạy lại red-team; ngưỡng trong `config/eval.yaml` chỉ đổi qua ADR.
- Kịch bản lừa đảo trong `drills/` chỉ ở **mức dấu hiệu hành vi**: không lời thoại hoàn chỉnh, không link/số tài khoản/tên cơ quan thật, gắn nhãn "Đây là mô phỏng"; validator từ chối vi phạm. Nhà nghiên cứu bên ngoài muốn đóng góp kịch bản gửi qua PR với cùng ràng buộc.
- Chúng tôi hoan nghênh báo cáo có trách nhiệm và ghi công trong CHANGELOG nếu người báo cáo đồng ý.

## Prompt log và dữ liệu xuất bản

Prompt log là minh chứng bắt buộc của BTC và **không được sửa tay**; trước khi lên Google Drive/ZIP, `make promptlog-export` kiểm tra hash khớp `docs/prompt-log/INDEX.md`, quét secret (gitleaks) và PII (regex), tự động thay bằng `[REDACTED-SECRET sha256:<8>]` / `[REDACTED-PII sha256:<8>]` và ghi `REDACTIONS.md` — đây là chính sách công bố, không phải chỉnh sửa nội dung. Dữ liệu pilot thô không bao giờ vào repo hay Drive.

## Phiên bản được hỗ trợ

Dự án đang ở giai đoạn prototype, chưa có bản phát hành gắn tag; chỉ nhánh `main` nhận bản vá bảo mật. Khi có tag (`v0.1`, `v0.5`, `v1.0`), chỉ tag mới nhất và `main` được hỗ trợ.
