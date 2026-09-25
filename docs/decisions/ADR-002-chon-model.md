# ADR-002 — Chọn model (planner, planner_small, VLM, ASR, TTS, embed/rerank, detector)

Ngày: 2026-09-18 · Người quyết: người dùng (đổi model là điểm dừng bắt buộc — plan §6) · Trạng thái: **chốt** cho planner/planner_small/ASR/embed/rerank/detector; **đề xuất, chờ người dùng** cho VLM (D9) và TTS · Liên quan: `config/models.yaml`, `data/registry/models.yaml`, D7–D10, D29; C03/F02, F03, F04, F06, F07, F08, LIC-07/08/09, C03-gap

## Bối cảnh
Ba file gốc ghi "Qwen3.5-1.7B" (không tồn tại — dải nhỏ Qwen3.5 là 0.8B/2B/4B/9B), PhoWhisper "Apache-2.0" (sai, là BSD-3-Clause), "YOLO" chung chung (Ultralytics là AGPL-3.0, không tương thích Apache-2.0 của repo), và giữ Qwen3-VL-8B riêng dù Qwen3.5 đã đa phương thức native; hai instance vLLM + KV cache 50 người không vừa GPU 24 GB và vLLM không hot-swap model (F03). TTS chưa có tiêu chí chọn (F06). Model sinh dữ liệu phải có ToS cho phép dùng đầu ra (LIC-09).

## Lựa chọn
| Vai trò | Model | Giấy phép | Cách chạy | Trạng thái |
| --- | --- | --- | --- | --- |
| `planner` | `Qwen/Qwen3.5-9B` + LoRA (E07), AWQ 4-bit | Apache-2.0 | vLLM, profile `gpu` | chốt |
| `planner_small` | `Qwen/Qwen3.5-2B` GGUF Q4_K_M (không có bản 1.7B — D8) | Apache-2.0 | llama.cpp server, profile `cpu`: dev Windows, CI demo, hackathon, tầng luôn bật/fallback chung kết (D29). **Không** còn là "model APK" (APK → hướng phát triển, ADR-006) | chốt |
| `quarantine`, `judge` | cùng base Qwen3.5-9B, prompt riêng, không tool, schema kín (SEC-03) | Apache-2.0 | vLLM cùng instance | chốt |
| `vlm` | **Đề xuất (D9 v2):** cùng `Qwen/Qwen3.5-9B` (đa phương thức native): lượt đọc ảnh dùng base, lượt huấn luyện viên dùng LoRA adapter (vLLM multi-LoRA), `--limit-mm-per-prompt image=1`, `--max-model-len 4096`. **Phương án B:** `Qwen/Qwen3-VL-8B-Instruct` (Apache-2.0) instance riêng — chỉ khi GPU ≥ 48 GB. **Phương án C:** vLLM chưa hỗ trợ AWQ + multi-LoRA + vision cùng lúc → `Qwen3.5-4B` bf16 làm cả planner lẫn VLM | Apache-2.0 | vLLM | **CÂU HỎI MỞ — người dùng chốt tại PR E01** sau spike 2 giờ trên máy GPU (điều kiện chốt: AWQ + LoRA + ảnh vào cùng instance, 20 lượt đọc ảnh sandbox đúng `screen_id` ≥ 18/20, KV cache đủ 50 phiên) |
| `asr` / `asr_small` | `vinai/PhoWhisper-small` / `PhoWhisper-tiny`, faster-whisper INT8 | **BSD-3-Clause** (D10; idea §15.4 sai) | GPU / CPU | chốt; ASR LoRA → BACKLOG |
| `tts` | Ứng viên: **Piper vi_VN** (MIT, RTF CPU thấp, giọng máy hơn), **F5-TTS-Vietnamese** (flow-matching, 1–3 s/câu, checkpoint thường CC-BY-NC-4.0 → xung đột tự host/redistribute), **viXTTS** (giấy phép checkpoint chưa rõ, phải đọc thẻ model). Tiêu chí quyết: (1) giấy phép MIT/Apache/BSD cho **cả code lẫn checkpoint**, cho phép tái phân phối và Tỉnh đoàn tự host; (2) RTF trên CPU < 0,3; (3) có giọng tiếng Việt sẵn; (4) MOS với 10 người cao tuổi ≥ 4/5 (idea §6) — nếu không đạt, báo cáo trung thực với mục tiêu tối thiểu ≥ 3,5 (F06). Mặc định kỹ thuật khi chưa chốt: Piper + stream theo câu + cache ~500 câu | xem cột trước | `services/speech` | **đề xuất, chờ MOS ở pilot sơ bộ 26–27/9**; nếu chọn model NC phải kê khai NC và ghi hạn chế triển khai ở mục 11/12 hồ sơ (LIC-08) |
| `embed` / `rerank` | `BAAI/bge-m3` / `BAAI/bge-reranker-v2-m3` | MIT | Qdrant hybrid | chốt |
| `ui_detector` | **YOLOX-Tiny** (Megvii, Apache-2.0) thay Ultralytics YOLO (AGPL-3.0) — D7; **không train ở v1.0** (F08/N06), giữ trong registry cho hướng phát triển | Apache-2.0 | onnxruntime | chốt (giấy phép), hoãn (huấn luyện) |
| Sinh dữ liệu / judge (E06) | mặc định `judge` tự host (Qwen3.5-9B, Apache-2.0 — không vướng ToS); nếu dùng API: chỉ model mở qua nhà cung cấp mà ToS không cấm dùng output để huấn luyện; kê khai `generator_model`, `generator_license`, `tos_url`, `tos_checked_on` (LIC-09) | — | — | chốt nguyên tắc; provider cụ thể chốt ở E06 |

Ma trận dự phòng fine-tune (F04): bf16 LoRA seq 4k OOM → QLoRA nf4 hoặc seq ≤ 2.048 + packing; AWQ lỗi → FP8 trên RTX 4090 (chốt 4090, bỏ A10G); PEFT chưa hỗ trợ Gated-DeltaNet → LoRA trên Qwen3.5-4B; llama.cpp chưa hỗ trợ Qwen3.5 → đường CPU dùng Qwen3-4B GGUF tạm và ghi rõ. Toolchain smoke trong `make doctor GPU=1` trước khi đặt lịch train.

## Hệ quả
- `config/models.yaml` đã phản ánh bảng này (vlm `status: proposed`, tts `TBD-ADR-002`); `.env.example` `VLM_MODEL` phải đổi theo quyết định D9; `deploy/docker-compose.yml` profile `gpu` chỉ 1 instance vLLM nếu chốt "một model".
- Ablation E07 đổi dòng "VLM đơn vs YOLOX+VLM" thành "VLM có/không JSON schema + grounding"; dòng "9B vs 2B tại chỗ" chỉ khi cùng điều kiện (F02).
- Bản kê khai (`make declaration`) đọc registry nên tự đúng giấy phép; idea.md/plan.md/prompt.md chỉ có errata (D31).
- Rủi ro: chờ quyết định D9 chặn E08; TTS NC làm khó "Tỉnh đoàn tự host"; VRAM 24 GB chật nếu thêm ASR GPU + reranker (đo ở spike).

## Trạng thái
2026-09-18 đề xuất (v2 brief). Chờ người dùng: (1) chốt D9 sau spike 2 giờ trên máy GPU (hạn: trước E08, tốt nhất tại PR E01); (2) chốt TTS sau MOS pilot sơ bộ 27/9 (hạn: trước E04 đủ; E04 Pha A chạy mặc định Piper). Xem lại khi eval vision < ngưỡng chặn 2 lần hoặc vLLM đổi hỗ trợ.
