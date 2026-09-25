---
name: test-strategy
description: Chiến lược kiểm thử 6 tầng của CTCV (prompt.md §7) — unit, tích hợp, e2e Playwright 3 viewport, phi chức năng, chất lượng AI (eval), an toàn (red-team); quy tắc fixture/seed, record/replay, bất biến, cổng make check vs make gate. Use when writing, reviewing or running tests, or deciding what to test.
---
# Chiến lược kiểm thử CTCV

## Sáu tầng
| Tầng | Loại | Công cụ | Ai viết | Ngưỡng |
| --- | --- | --- | --- | --- |
| 1. Đơn vị | Hàm, tool, guardrail, máy trạng thái, schema, token UI | pytest, vitest | dev viết trước khi code; qa-tester bổ sung | Coverage ≥ 80 % cho `ctcv_agent`, `ctcv_sandbox`, `ctcv_api` (ép bởi `make unit`) |
| 2. Tích hợp | API ↔ DB ↔ Redis ↔ Qdrant ↔ vLLM (mock có ghi) | pytest + testcontainers (`@pytest.mark.integration`, từ E02) | qa-tester | Mọi endpoint có **test hợp đồng** (schema request/response, kể cả stub 501) |
| 3. E2E | Kịch bản sandbox bằng giọng nói giả lập (audio file) trên 3 viewport; dashboard; kèm cặp | Playwright (`E2E=1 make e2e`, MCP playwright để chụp) | qa-tester | 100 % kịch bản đã ship; ảnh vào `docs/screens/YYYY-MM-DD/` |
| 4. Phi chức năng | Tải, độ trễ, a11y, Lighthouse, restore-drill | k6 (`eval/loadtest/k6.js`), axe, Lighthouse | qa-tester + devops | p95 < 2,5 s; a11y 0 lỗi nghiêm trọng; Lighthouse ≥ 90 |
| 5. Chất lượng AI | Q&A trích dẫn, hội thoại, ảnh, audio, ablation | `make eval [QUICK=1]` (ngưỡng `config/eval.yaml`) | qa-tester + ml-trainer | accept/block theo 6 bộ; LLM-judge hiệu chỉnh bằng 100 mẫu người chấm |
| 6. An toàn | Red-team, PII, prompt injection | `make redteam` (guardrails thuần) · `make redteam-model` | security-redteam | 0 lỗi |

## Hai cổng (D13)
- `make check [QUICK=1]` = **tất định, không model**: lint · unit · integration · redteam (thuần) · audit · docs-check (+ e2e, build khi `QUICK≠1`); chạy mỗi PR trên GitHub-hosted; ghi `docs/status/last_check.json`.
- `make gate` = cần GPU/staging: eval QUICK=1 (LLM-judge) · redteam-model · loadtest; hằng đêm trên runner máy GPU và trước mỗi tag. CI không bao giờ gọi model.
- Trong lúc làm: `uv run pytest <thư mục gói>`; hook test: `uv run pytest .claude/hooks/tests`.

## Quy tắc để test có giá trị thật
1. Test viết **trước** từ tiêu chí nghiệm thu trong epic; một hành vi = một test có tên tiếng Anh mô tả (`test_router_rejects_tool_not_in_whitelist`).
2. Fixture và seed cố định; dữ liệu test sinh từ pipeline với `--limit`, không chép tay; **không gọi model thật** ngoài tầng 5 — record/replay cho vLLM; SQLite in-memory cho unit (kiểu cột generic `Uuid`, `JSON` — D15).
3. Cấm `skip`/`xfail` mới không có ADR; cấm nới ngưỡng `config/eval.yaml` (hook `protect-paths` chặn, chỉ ADR + `CTCV_ALLOW_EVAL_THRESHOLD=1`); cấm xóa test để xanh; coverage không giảm.
4. `tests/invariants/` có test riêng cho (a) tool whitelist + `SIDE_EFFECT ∈ {none, sandbox, log}` + module tool không import httpx/requests/subprocess; (b) không PII trong fixture/log mẫu, model DB không cột CCCD/OTP/password; (c) `requires_citation` bắt câu dữ kiện không nguồn; (d) taint — không chuỗi untrusted vào prompt planner.
5. Mọi lỗi từ red-team hoặc pilot → **test hồi quy trước khi sửa**.
6. Test hook Claude Code chạy hook như subprocess với JSON stdin, gồm cả biến thể vòng qua (`rm -fr`, `--no-verify`, `core.hooksPath`, đọc `.env` qua pipe).

## Báo cáo lỗi (qa-tester)
Mỗi lỗi: cách tái hiện (lệnh), log 20 dòng, vị trí nghi ngờ, mức (P1 vi phạm bất biến/rò rỉ · P2 sai hợp đồng · P3 khác). Đánh giá AI: tách dev/test, báo cáo theo lát cắt (giọng vùng miền, nhóm tuổi, kỹ năng), ablation từng thành phần, ghi rõ "kết quả chưa đạt". Người chấm cuối là người dùng pilot, không phải benchmark.

## Vòng tự vận hành
dev (PR draft) → qa-tester (test + `make check`) → đỏ quay lại dev / xanh → reviewer (DoD) → chạm agent/guardrail/tool/hook/permissions → security-redteam → orchestrator mở PR có checklist ≤ 30 phút cho người dùng (những gì máy không kiểm được: câu chữ, cảm giác dùng, độ "thật" của mô phỏng).
