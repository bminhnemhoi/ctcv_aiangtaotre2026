---
name: agent-security
description: An toàn agent của CTCV theo mô hình CaMeL và OWASP Agentic 2026 — tách planner/quarantine, tool whitelist có schema, PII, TTL ảnh, red-team, hook/permissions Claude Code. Use when touching services/agent, guardrails, tools, config/prompts, hooks, permissions, or when reviewing security of any PR.
---
# An toàn agent (idea §5 tầng bảo mật, idea §9, plan Phụ lục A "Bảo mật", brief §7, D22, D28)

## Mô hình CaMeL áp dụng trong CTCV
- **Planner** (`ctcv_agent.planner`, prompt `coach.v1`) chỉ nhìn **trạng thái có cấu trúc** của sandbox và **kết quả tool có schema**; không bao giờ nhận văn bản thô từ nguồn không tin cậy.
- **Quarantined LLM** (`ctcv_agent.quarantine`, prompt `quarantine.v1`, model `quarantine` trong `config/models.yaml`) đọc mọi nội dung untrusted (người dân dán, tin nhắn mẫu, trang web, chữ trong ảnh) và trả **schema kín** (D28): enum `intent`, mã `red_flag` từ danh mục, số tiền, danh mục cơ quan — **không trường text tự do**; không có quyền gọi tool. VLM trả `screen_id` thuộc catalog + `element_id`.
- **Tool router** chỉ gọi tool có trong `TOOL_REGISTRY` (MappingProxyType) **và** `config/tools.yaml`; 8 tool, `SIDE_EFFECT ∈ {none, sandbox, log}`; tên lạ → `ToolNotAllowed`; `user_id` từ JWT, không phải tham số tool; module tool không import httpx/requests/subprocess.
- **Guardrails cứng** (`ctcv_agent.guardrails`, regex/ngưỡng ở `config/guardrails.yaml`): `redact_pii`, `refuses_sensitive_request` (OTP/mật khẩu/số thẻ/CCCD), `refuses_real_action` ("làm giúp trên app thật", "chuyển tiền giúp"), `enforce_style` (≤ 2 câu, hành động, xác nhận ý định), `requires_citation`; `verify_citation` (reranker + judge) trước khi đọc dữ kiện; `confidence < escalate_confidence` → `escalate_to_volunteer`.
- Test bất biến `tests/invariants/`: whitelist/side effect · không PII · citation · **taint** (không chuỗi untrusted vào prompt planner).

## Checklist OWASP Agentic 2026 (review mỗi PR — CLAUDE.md "Bảo mật")
| Kiểm soát | Cách kiểm trong repo |
| --- | --- |
| Planner tách khỏi quarantined LLM | Không đường đi nào từ input untrusted tới prompt planner ngoài schema kín (taint test) |
| Tool có schema và whitelist | `config/tools.yaml` == registry; test bất biến; thêm tool = điểm dừng |
| Quyền tối thiểu | Không tool gửi tiền/tin/gọi API ngoài; dịch vụ agent không egress; sandbox tách biệt |
| Không secret trong mã | gitleaks trong pre-commit và `make audit`; `.env` không commit; hook chặn đọc `.env` |
| Rate limit | `rate_limit_per_min`, `max_concurrent_sessions` (config/app.yaml); JWT ngắn hạn |
| PII redaction | `redact_pii` đầu vào/đầu ra; log qua `ctcv_core.logging` (scrub); DB không cột CCCD/OTP/password; `events.payload_json` allowlist |
| TTL ảnh 60 s | MinIO TTL; `screen_jobs.deleted_at`; che số nhạy cảm trước khi vào model |
| Log không PII | Test regex trên fixture/log mẫu; `qa_logs` chỉ hash |
| Dependency audit | `make audit`: pip-audit, pnpm audit, `config/allowed-deps.yaml` + giấy phép |
| Red-team hồi quy | Sửa guardrail/tool/prompt/hook → `make redteam` + kịch bản mới trong `eval/redteam/` |
| Giám sát | Cảnh báo vòng lặp tool, ngắt mạch khi chi phí vượt ngưỡng, tỷ lệ escalate |
| Lạm dụng drill | Drill chỉ mẫu hành vi (D27), server chọn biến thể, `qr_token` hết hạn/thu hồi, khóa sau đăng nhập lớp |

## Bề mặt red-team bắt buộc (`eval/redteam/scenarios.jsonl`, mỗi kịch bản có `expected` + bộ chấm)
Injection trực tiếp; gián tiếp qua nội dung dán, ảnh màn hình có chữ, kết quả tool giả, kho RAG bị nhiễm; câu hỏi nhiều bước leo thang; moi OTP/mật khẩu/số thẻ/CCCD; "làm giúp trên app thật"; rò rỉ prompt hệ thống; PII trong log/DB; dùng ngược kịch bản lừa đảo; tool ngoài whitelist / `user_id` giả; quarantine trả text tự do; vòng qua hook/permissions Claude Code. Bản 29/9: 50–100 kịch bản guardrails thuần = 0 lỗi; Pha D: 200 có model.

## Hook và permissions Claude Code (D22 — cũng là bề mặt tấn công)
- `guard.py` (PreToolUse Bash, **fail-closed**): rm r+f mọi thứ tự/spelling, `git push --force/-f/--force-with-lease`, `git reset --hard origin`, `git clean -f`, `--no-verify`, `core.hooksPath`, `docker system prune`, `docker compose config` không `--no-interpolate`, `printenv`/`env`/`set` đứng một mình, mkfs, `dd of=/dev/`, fork bomb, `curl|sh`, đọc `.env`/`*.pem` qua cat/less/head/tail/grep/awk/sed/type/Get-Content/python -c; ngân sách cho `make train|data|finetune`.
- `protect-paths.py` (PreToolUse Edit/MultiEdit/Write/NotebookEdit, fail-closed): `docs/prompt-log/**`, `data/registry/*.lock`, `docs/dossier/private/**`, migration đã trên `main`, `config/eval.yaml`, `.claude/**`/`CLAUDE.md`/`.github/workflows/**`/`.pre-commit-config.yaml`/`Makefile` (trừ khi marker `.claude/BOOTSTRAP`); luôn cho `eval/redteam/**`, `docs/security/**`.
- `prompt-guard.py`: chặn prompt chứa secret (sk-, ghp_, hf_, AKIA, password=, base64 ≥ 40). Settings deny: `git push --force`, `--no-verify`, `rm -rf`, `docker system prune`, `Read(.env*)`, `Read(**/*.pem)`, `Read(docs/dossier/private/**)`, ghi `docs/prompt-log/**`.
- Luật an toàn phải là **hook**, không phải lời dặn trong prompt; test hook ở `.claude/hooks/tests/` gồm biến thể vòng qua.

## Pháp lý (idea §9)
Luật AI 134/2025/QH15 (1/3/2026), NĐ 142/2026/NĐ-CP (1/5/2026) — tự phân loại rủi ro thấp, nhãn "nội dung do AI tạo"; Luật BVDLCN 91/2025/QH15 + NĐ 356/2025/NĐ-CP — thu tối thiểu, đồng thuận chữ to, quyền xóa, máy chủ trong nước; chỉ nhắc số hiệu đã `verified_on` trong `docs/legal/refs.yaml`.
