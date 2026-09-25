# ADR-004 — Tách planner khỏi quarantined LLM (CaMeL) bằng ranh giới module, whitelist tool và schema kín

Ngày: 2026-09-18 · Người quyết: orchestrator E01 theo brief §7, D28, §17.7 · Trạng thái: **chốt** (kiểm chứng lại tại E05 với security-redteam) · Liên quan: idea §5 (CaMeL), plan §5 (tool), E05, E08, E09; SEC-03, SEC-04, SEC-05, SEC-06

## Bối cảnh
Agent đọc văn bản không tin cậy (tin nhắn dán, trang web, ảnh màn hình, kết quả tool) nên dễ bị prompt injection; nguyên tắc CaMeL đã có trong idea/plan nhưng chưa đặc tả "tóm tắt có cấu trúc" là gì, `user_id` còn là tham số tool, và chưa có test taint (SEC-03).

## Lựa chọn
- **Nguyên tắc:** planner **không bao giờ nhận chuỗi tự do có nguồn gốc không tin cậy**. Mọi thứ vào planner là: trạng thái sandbox có cấu trúc, kết quả tool có schema Pydantic, đối tượng kín từ quarantine, chunk RAG đã verify.
- **Ranh giới module** (`services/agent/src/ctcv_agent/`): `planner.py` (chỉ import `router`, `guardrails`, schema); `quarantine.py` (không import `tools`/`router`, không có quyền gọi tool, model `quarantine` trong `config/models.yaml`, prompt `quarantine.v1.md`); `router.py` (chỉ gọi tool có trong `TOOL_REGISTRY` MappingProxyType **và** trong `config/tools.yaml`; tên lạ → `ToolNotAllowed`); `tools/*.py` (Input/Output Pydantic, `SIDE_EFFECT ∈ {none, sandbox, log}`, không import `httpx`/`requests`/`subprocess`).
- **Quarantine trả schema kín** (D28): `QuarantineOut{intent: enum, red_flags: list[RedFlagCode], amount: int|null, agency: AgencyCode|null, confidence}` — không trường text tự do; Pydantic `extra="forbid"`.
- **VLM** (E08) trả `screen_id ∈ catalog` + `element_id` + `pii_bboxes`, không text; post-filter chặn chuỗi số ≥ 4 ký tự.
- **RAG**: chunk chỉ vào planner sau `verify_citation`, bọc nhãn nguồn `[NGUỒN: <agency>, <date>]`, lọc câu mệnh lệnh bằng regex, tối đa N câu (`config/guardrails.yaml`).
- **`user_id`** lấy từ JWT trong ngữ cảnh phiên, không phải tham số tool; `log_progress` đọc từ ngữ cảnh.
- **Đầu ra planner** qua `enforce_style` (≤ 2 câu, hành động cụ thể, xác nhận ý định lượt đầu, không `banned_terms`) và `redact_pii` trước khi tới TTS/UI.
- **Test bất biến** (`tests/invariants`): (a) whitelist + side effect; (d) taint — mọi hàm xây prompt planner từ chối tham số kiểu `str` có nhãn untrusted (kiểu `Untrusted[str]` không được đưa vào template); red-team `eval/redteam/scenarios.jsonl` có ca injection qua nội dung dán, ảnh, kết quả tool giả, câu hỏi nhiều bước.

## Hệ quả
- Injection chỉ có thể làm quarantine phân loại sai, không thể gọi tool hay đổi hướng dẫn; bề mặt kiểm thử nhỏ, đo được bằng `make redteam` (guardrail thuần) và `make redteam-model`.
- Chi phí: một lượt quarantine thêm ~0,3–1 s khi có nội dung dán (chỉ ở `/coach/ask` với input dán/ảnh, không ở bước sandbox).
- Mọi thay đổi ở `guardrails.py`, `router.py`, `tools/`, `config/tools.yaml` phải qua `security-redteam` + test hồi quy (prompt §2 quy tắc 3).

## Trạng thái
2026-09-18 chốt cho E01 (skeleton + test bất biến); E05 hiện thực đầy đủ và chạy red-team 50; E11 mở rộng 200. Xem lại nếu red-team phát hiện lỗ hổng cấu trúc (không chỉ regex).
