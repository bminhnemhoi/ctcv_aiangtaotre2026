---
name: tthc-verify-layers
description: Kiến trúc kiểm chứng CaMeL của /v1/coach/ask và các điểm mù đã tìm ra (tính đến 25/9/2026 — cần kiểm lại vì có thể đã vá)
metadata:
  type: project
---

Đường đi một câu hỏi trong `ctcv_agent/ask.py::AnswerEngine.ask` (đọc kèm để cập nhật, mã có thể đổi):
`_safety` (sensitive/real_action/pasted) → `redact_pii` → `_route` (intent + hybrid search + gate) → composer soạn 1 câu → `_check_sentence` → nếu rớt thì câu mẫu `answer_templates.py` hoặc "chưa chắc".

**Composer KHÔNG được tin.** Câu chỉ thành `llm_verified` khi qua `_check_sentence`: `_form_rejection` (script/length/1 câu), `_content_rejection` (`refuses_sensitive_request`/`asks_real_action`/`redact_pii`), `numbers_supported`, `_fee_rejection` (claims_free/channel mismatch), `_condition_rejection`, `_case_rejection`, lexical floor. Đối chứng IC-K01…K07 xác nhận các lớp này chặn thật.

**Why (điểm mù đã tìm, 25/9 — cần re-verify trước khi tin):**
- **Kiểm số chỉ so chuỗi chữ số, KHÔNG biết đơn vị** (`numeric.py::numbers_supported`). Câu "160.000 đô la" hay "07 tháng" qua được vì 160000/7 có trong nguồn (nguồn ghi "đồng"/"ngày"). Đây là F-01 High của báo cáo 2026-09-25.
- **`refuses_sensitive_request` / `asks_real_action` / `looks_like_pasted_content` chỉ có mẫu tiếng Việt CÓ DẤU** (`config/guardrails.yaml`). Biến thể không dấu ("mat khau", "nop giup"), đòi OTP không dùng chữ "OTP" ("mã 6 số vừa về máy") lọt phân loại → chỉ rơi "chưa chắc" thay vì câu cảnh báo. Câu mẫu vẫn an toàn (không lộ, không hành động).
- **Regex PII (`cccd` 12 số liền, `phone` 10 số liền) bỏ sót số viết cách nhóm** ("001 234 567 890", "0912.345.678"). Lọt tới composer/log.
- **Câu MẪU tất định KHÔNG chạy `_content_rejection`** → nếu bản ghi bị nhiễm (crawl độc), câu mẫu chép nguyên văn link/SĐT trong tên cơ quan/bước đầu. Tuyến chính bảo vệ là toàn vẹn nguồn (sha256 manifest, chỉ crawl https dichvucong.bocongan.gov.vn).

**How to apply:** khi P3 báo đã vá, chạy lại các đối chứng IC-A0x/IC-Q0x (script mẫu trong báo cáo) trước khi coi là kín. `intake-check` từng ném 500 với bản ghi 1.002757 (message 3 câu) và chặn cán bộ với case_label >300 ký tự của 1.004222.

Xem [[effective-attacks-tthc]], [[harness-and-attack-setup]].
