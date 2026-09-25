# 6. Quy trình huấn luyện, tinh chỉnh, tích hợp hoặc khai thác mô hình (nếu có)

> Nội dung trình bày: Mô tả ngắn cách đội thi huấn luyện, tinh chỉnh, tích hợp hoặc khai thác mô hình trí tuệ nhân tạo; nêu dữ liệu đầu vào, cách thiết lập, cách kiểm tra và điều chỉnh mô hình (nếu có).

Đội phân biệt **đã làm** (có test hoặc số đo ở mục 8) và **kế hoạch** có ngày cụ thể; kế hoạch không được tính là kết quả.

## 6.1. Trạng thái tại ngày lập hồ sơ ({{eval:engineering.date_vi|19/9/2026}})

| Hạng mục | Trạng thái | Minh chứng |
| --- | --- | --- |
| Lớp khai thác mô hình: client chuẩn OpenAI cho vLLM/llama.cpp, đầu ra JSON có cấu trúc, ghi–phát lại để kiểm thử tất định; bốn prompt có phiên bản | **Đã làm** (E01) | {{eval:engineering.python_tests.passed|—}} test tự động đạt; độ phủ mã lõi {{eval:engineering.coverage.percent|—}} % |
| Guardrail cứng, whitelist {{eval:engineering.agent.tools|8}} tool có schema, LLM cách ly trả schema kín, kiểm chứng trích dẫn mức từ vựng | **Đã làm** (E01) | Red-team {{eval:engineering.redteam.size|50}} kịch bản không cần mô hình: {{eval:engineering.redteam.leaks|0}} rò rỉ |
| Sandbox engine + validator; schema, validator và chấm điểm vắc-xin lừa đảo | **Đã làm** (E01) | Một kịch bản mẫu mỗi loại; {{eval:engineering.sandbox.invalid_fixtures_rejected|26}} + {{eval:engineering.drills.invalid_fixtures_rejected|26}} ca lỗi cố ý bị từ chối |
| Phục vụ Qwen3.5-9B qua vLLM (AWQ) và đường CPU Qwen3.5-2B (llama.cpp) | Kế hoạch Pha A (đến 29/9) | Cần máy GPU thuê |
| PhoWhisper-small (faster-whisper INT8) và Piper TTS có cache | Kế hoạch Pha A | WER theo lát cắt trên 1 giờ audio |
| Truy xuất bge-m3 + reranker trên kho hướng dẫn, kiểm chứng trích dẫn bằng reranker | Kế hoạch Pha A | Recall@5, citation-support |
| Bộ sinh dữ liệu tổng hợp và bộ lọc | Kế hoạch Pha A (200 hội thoại đánh giá) → Pha D (8.000 SFT / 2.000 DPO) | — |
| Fine-tune LoRA SFT + DPO cho planner; VLM đọc ảnh sandbox | Kế hoạch Pha D (19/10–17/11/2026) | Bảng ablation |
| Huấn luyện YOLOX-Tiny; LoRA giọng cho ASR; APK offline | Hoãn / tùy chọn | BACKLOG kèm điều kiện kích hoạt |

Bảng được cập nhật tại ngày gắn tag nộp; một hàng chỉ chuyển sang "Đã làm" khi có test hoặc số đo ở mục 8.

## 6.2. Lộ trình tinh chỉnh huấn luyện viên (kế hoạch, `make train` trên 1 GPU 24 GB)

1. **Dữ liệu đầu vào:** 8.000 hội thoại SFT và 2.000 cặp DPO sinh theo mục 4 (bước 6), chia train/dev/test theo kịch bản để tránh rò rỉ; cặp DPO đối lập "ngắn, một bước, có xác nhận ý định" với "trả lời dài kiểu chatbot".
2. **Thiết lập:** SFT LoRA r = 16, alpha = 32, lr 1e-4, 2 epoch có dừng sớm; **QLoRA nf4** hoặc bf16 với `seq_len ≤ 2.048` + packing + flash-attention; DPO beta 0,1, 1 epoch, dừng khi reward margin ≥ 0,5. `make doctor GPU=1` chạy "toolchain smoke" (tải mô hình, 10 bước LoRA, merge, `vllm serve`) trước lần chạy thật để phát hiện sớm PEFT/AWQ chưa hỗ trợ Qwen3.5.
3. **Lượng tử hóa và phục vụ:** merge adapter vào bf16 rồi lượng tử hóa AWQ 4-bit để vLLM phục vụ đúng một mô hình; AWQ lỗi thì dùng FP8 trên RTX 4090 (ma trận dự phòng trong ADR-002). GGUF Q4_K_M của Qwen3.5-2B chỉ phục vụ đường CPU dự phòng.
4. **Kiểm tra và điều chỉnh:** bộ 200 (→ 500) hội thoại giữ lại đo độ ngắn, tỷ lệ hành động cụ thể, xác nhận ý định, không hallucination; ngưỡng chấp nhận/chặn trong `config/eval.yaml` chỉ đổi qua ADR; không thay mô hình đang phục vụ khi eval dưới ngưỡng chặn; bảng ablation sinh tự động; mỗi lần chạy ghi config, log, metrics, thẻ mô hình vào `training/runs/`; checkpoint được chọn ghi vào `data/registry/models.yaml`.
5. **Ngân sách:** 300 giờ GPU; tác vụ > 20 giờ GPU hoặc > 500.000 đồng API phải được duyệt trước (hook chặn).

## 6.3. Tích hợp và khai thác

Mọi mô hình phục vụ qua giao diện OpenAI-compatible của vLLM (cổng 8040) hoặc llama.cpp; dịch vụ `agent` chỉ biết tên mô hình trong `config/models.yaml` nên đổi mô hình không cần đổi mã. Kiểm chứng trích dẫn đồng bộ dùng điểm reranker; LLM-judge chỉ chạy offline trong `make eval` để không cộng thêm độ trễ. TTS sinh sẵn cho tập hữu hạn câu huấn luyện viên theo (kịch bản, màn hình, lỗi) nên bước sandbox không gọi mô hình trực tuyến. Đổi mô hình là điểm dừng bắt buộc: phải có ADR và số eval trước/sau.
