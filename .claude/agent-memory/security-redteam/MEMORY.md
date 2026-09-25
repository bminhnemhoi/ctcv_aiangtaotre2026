# Security red-team memory — CTCV

- [Red-team harness & how to attack CTCV](harness_and_attack_setup.md) — 3 kênh: make redteam (DummyPlanner), live qua dev_cpu.py --run, inproc với FakeComposer; cách gọi hook từ Python
- [TTHC verify layers & blind spots](tthc_verify_layers.md) — kiến trúc CaMeL của /coach/ask và các điểm mù đã tìm (kiểm số không biết đơn vị, guardrail chỉ có mẫu có dấu, regex PII bỏ sót số cách nhóm)
- [Effective attack patterns on /coach/ask](effective_attacks_tthc.md) — mồi đổi đơn vị/tiền tệ, câu nhạy cảm không dấu, PII cách nhóm, nguồn bị nhiễm
- [Pre-publish audit patterns](prepublish_audit_patterns.md) — điểm mù gitleaks/redaction export, secret/PII ẩn trong transcript Claude Code, mẹo né false-positive của hook
- [Mask before print](feedback_mask_before_print.md) — không in cửa sổ ngữ cảnh quanh chuỗi giống credential; output của agent này bị chép vào docs/prompt-log
- [Pre-publish state 2026-09-25](project_prepublish_2026_09_25.md) — kết luận audit công khai repo DFL và những gì phải kiểm lại lần sau
