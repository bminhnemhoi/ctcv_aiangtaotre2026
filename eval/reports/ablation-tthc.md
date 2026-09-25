# Ablation hỏi đáp thủ tục — 2026-09-25

Tập `test`, 138 câu; ba chế độ lấy từ cùng một lượt gọi mô hình (xem `eval/README.md`). Sinh tự động, không sửa tay.

| Chế độ | Ảo giác (%) | Số đúng nguồn (%) | Trả lời đúng (%) | p50 (s) | p95 (s) | Đã trả lời |
| --- | --- | --- | --- | --- | --- | --- |
| template_only | 0 | 100 | 85.22 | 0.047 | 0.057 | 101 |
| llm_unverified | 14 | 98.82 | 84.35 | 0.907 | 1.626 | 100 |
| llm_verified | 0 | 100 | 86.09 | 0.908 | 1.629 | 102 |

Câu do mô hình viết được giữ sau kiểm chứng: 68 % (trên 100 câu mô hình đề xuất khi đã qua cổng).
