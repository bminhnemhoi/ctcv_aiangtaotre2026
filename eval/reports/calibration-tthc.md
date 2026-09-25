# Hiệu chỉnh cổng trả lời TTHC — 2026-09-25

Tập `dev`: 64 câu cần trả lời, 11 câu cần từ chối hoặc chuyển người. Sinh bởi `uv run python -m ctcv_eval.calibrate_tthc`; không tự sửa `config/rag.yaml`.

Cấu hình hiện tại: min_dense_score = 0.45, title_overlap_min = 0.34.

| min_dense_score | title_overlap_min | refusal_accuracy (%) | false_escalation_rate (%) |
| --- | --- | --- | --- |
| 0.35 | 0.2 | 81.82 | 3.12 |
| 0.35 | 0.34 | 81.82 | 4.69 |
| 0.35 | 0.5 | 90.91 | 9.38 |
| 0.4 | 0.2 | 81.82 | 3.12 |
| 0.4 | 0.34 | 81.82 | 4.69 |
| 0.4 | 0.5 | 90.91 | 9.38 |
| 0.45 | 0.2 | 81.82 | 3.12 |
| 0.45 | 0.34 | 81.82 | 4.69 |
| 0.45 | 0.5 | 90.91 | 9.38 |
| 0.5 | 0.2 | 81.82 | 4.69 |
| 0.5 | 0.34 | 81.82 | 6.25 |
| 0.5 | 0.5 | 90.91 | 10.94 |
| 0.55 | 0.2 | 81.82 | 6.25 |
| 0.55 | 0.34 | 81.82 | 7.81 |
| 0.55 | 0.5 | 90.91 | 12.5 |
| 0.6 | 0.2 | 81.82 | 6.25 |
| 0.6 | 0.34 | 81.82 | 7.81 |
| 0.6 | 0.5 | 90.91 | 12.5 |
| 0.65 | 0.2 | 81.82 | 10.94 |
| 0.65 | 0.34 | 81.82 | 12.5 |
| 0.65 | 0.5 | 90.91 | 15.62 |

## Đề xuất

min_dense_score = 0.45, title_overlap_min = 0.5 (refusal_accuracy 90.91 %, false_escalation_rate 9.38 %). Người phụ trách quyết định có đổi hay không.
