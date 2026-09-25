# Độ trễ chỉ-CPU — hỏi đáp thủ tục (2026-09-25, lượt đo v2)

Sinh bởi script đo P14 lúc 2026-09-25T07:55:41Z từ `CTCV_OLLAMA_NUM_GPU=0 uv run python -m ctcv_eval.harness --suite qa --report-dir <thư mục tạm>`. Không thay `latest.json` (số đo chính có GPU).

- Máy: 12th Gen Intel(R) Core(TM) i5-12450HX, 8 lõi / 12 luồng, RAM 15,7 GB, Windows 11 (10.0.22631).
- Mô hình: `bge-m3:latest` (F16); `qwen3.5:2b` (Q8_0).
- Ép CPU: `CTCV_OLLAMA_NUM_GPU=0` → Ollama `options.num_gpu = 0`. Bằng chứng: `ollama ps` cuối lượt: qwen3.5:2b 100% CPU, bge-m3:latest 100% CPU; thăm dò mỗi 5 s trong lượt (212 mẫu): bge-m3:latest 100% GPU (Stopping...) × 1, bge-m3:latest 100% CPU × 210, qwen3.5:2b 100% CPU × 208.
- Tập `test`, 138 câu, chạy tuần tự; 2026-09-25T07:35:04Z → 2026-09-25T07:53:09Z.

## Độ trễ đầu-cuối (llm_verified, giây)

| Thiết bị suy luận | p50 | p95 |
| --- | --- | --- |
| GPU RTX 4050 Laptop (latest.json) | 0,908 | 1,629 |
| Chỉ CPU | 6,155 | 14,305 |

## Theo chế độ ablation (giây)

| Chế độ | GPU p50 | GPU p95 | CPU p50 | CPU p95 |
| --- | --- | --- | --- | --- |
| template_only | 0,047 | 0,057 | 2,164 | 2,231 |
| llm_unverified | 0,907 | 1,626 | 6,153 | 14,302 |
| llm_verified | 0,908 | 1,629 | 6,155 | 14,305 |

## Chất lượng trong lượt chỉ-CPU

| Chỉ số | Giá trị |
| --- | --- |
| recall_at_5 | 95,65 |
| answer_accuracy | 86,09 |
| citation_support | 100 |
| hallucination | 0 |
| numeric_fidelity | 100 |
| refusal_accuracy | 100 |
| false_escalation_rate | 11,3 |
| latency_p50_s | 6,155 |
| latency_p95_s | 14,305 |
| answer_accuracy_text_only | 68,7 |

network_hosts: localhost:11434; composer_failures: 0.

Chỉ số của câu trả lời cuối (llm_verified) trong lượt chỉ-CPU trùng lượt GPU; khác ở answer_accuracy_text_only (69,57 GPU / 68,7 CPU), tỷ lệ câu mô hình được giữ (68 % / 66 %) và chế độ llm_unverified (ảo giác 14 % / 15 %; số đúng nguồn 98,82 % / 97,67 %): phép tính số thực khác nhau giữa GPU và CPU nên câu chữ mô hình sinh ra lệch đôi chút dù temperature 0. Đo tuần tự từng câu; không chạy e2e, quay video hay make check song song; stack dùng thử của người dùng (cổng 8100/5273) vẫn bật nhưng không có lượt dùng được điều phối trong lúc đo. Độ trễ gồm cả embed truy vấn (bge-m3) trên CPU — vì vậy template_only cũng tăng lên ~2,2 s.
