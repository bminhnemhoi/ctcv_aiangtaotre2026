# deploy/models — phục vụ model (vLLM trên máy GPU, llama.cpp trên CPU)

Thư mục này **không chứa model**. `models` trong `deploy/docker-compose.yml` dùng image vLLM upstream (`vllm/vllm-openai`, không build — brief §17.10) và đọc cờ từ `deploy/models/vllm.env` (chép từ `vllm.env.example`, gitignore). Tên model, giấy phép và ngưỡng nằm ở `config/models.yaml`; đổi model là **điểm dừng bắt buộc** (ADR-002).

## Một model phục vụ tất cả (D9 v2 — đề xuất, chờ chốt)

| Vai (config/models.yaml) | Model gọi tới | Cách phân biệt |
| --- | --- | --- |
| `planner` (huấn luyện viên) | `Qwen/Qwen3.5-9B` + LoRA `coach` (sau E07) | multi-LoRA của vLLM: client gửi `model: coach` |
| `vlm` (đọc ảnh màn hình) | cùng base 9B, đa phương thức native | `model: Qwen/Qwen3.5-9B`, prompt `vlm_screen.v1`, kèm 1 ảnh |
| `quarantine`, `judge` | cùng base, prompt riêng, không tool | `model: Qwen/Qwen3.5-9B` |

Hai instance vLLM (9B + Qwen3-VL-8B) cộng KV cache cho 50 người **không vừa 24 GB** và vLLM không hot-swap model, nên "VLM tải theo yêu cầu" (idea §10) được hiện thực bằng **một server đa phương thức**: lượt đọc ảnh chỉ tốn thêm token ảnh trong cùng KV cache, không tốn VRAM trọng số. Phương án B (ADR-002): Qwen3-VL-8B riêng, bật tay khi cần bằng một service `models-vlm` thứ hai với `--gpu-memory-utilization 0.35` cho mỗi server (chỉ đủ cho demo, không đủ cho 50 người).

## Cờ vLLM (từ `vllm.env`; mặc định trong compose)

| Cờ | Biến | Mặc định | Ghi chú |
| --- | --- | --- | --- |
| `--model` | `VLLM_MODEL` | `Qwen/Qwen3.5-9B` | Trỏ vào checkpoint **AWQ 4-bit** (xuất từ `make train` bước lượng tử hóa ở E07, hoặc bản AWQ Apache-2.0 trên Hugging Face — ghi vào `data/registry/models.yaml`). Chưa có AWQ: chạy bf16 (`VLLM_QUANTIZATION=` rỗng, `VLLM_DTYPE=bfloat16`, `VLLM_MAX_NUM_SEQS=8`) — 9B bf16 ≈ 18 GB trọng số, KV cache còn rất ít |
| `--served-model-name` | `VLLM_SERVED_NAME` | `Qwen/Qwen3.5-9B` | Phải khớp `id` trong `config/models.yaml` |
| `--quantization` | `VLLM_QUANTIZATION` | `awq` | AWQ 4-bit ≈ 6–7 GB trọng số → ~14 GB còn lại cho KV cache |
| `--dtype` | `VLLM_DTYPE` | `half` | `half` cho AWQ; `bfloat16` cho base |
| `--max-model-len` | `VLLM_MAX_MODEL_LEN` | `4096` | Prompt coach + trạng thái sandbox + kết quả tool + ≤ 160 token trả lời. Tăng lên 8192 chỉ khi đọc ảnh cần (token ảnh) |
| `--gpu-memory-utilization` | `VLLM_GPU_MEMORY_UTILIZATION` | `0.90` | Cảnh báo `GpuMemoryHigh` nổ ở 92 % — giảm xuống 0.85 nếu OOM lặp 3 lần (RUNBOOK §6) |
| `--max-num-seqs` | `VLLM_MAX_NUM_SEQS` | `32` | 50 người dùng có think-time ≈ 8–12 lượt đồng thời |
| `--limit-mm-per-prompt` | `VLLM_LIMIT_MM_PER_PROMPT` | `image=1` | Mỗi lượt đọc màn hình đúng 1 ảnh (ảnh chỉ sống 60 s trong MinIO — ADR-005) |
| `--enable-prefix-caching` | (luôn bật) | — | Prompt hệ thống `coach.v1` dùng chung giữa mọi phiên |
| `--enable-lora --max-lora-rank 16 --lora-modules coach=/models/adapters/coach` | `VLLM_EXTRA_ARGS` | (chú thích) | Bật khi E07 có adapter; adapter đặt ở `deploy/models/adapters/coach/` (mount chỉ đọc) |
| `--tensor-parallel-size` | `VLLM_EXTRA_ARGS` | — | Chỉ khi thuê máy 2 GPU |

Kiểm tra sau khi lên: `curl -s http://localhost:8040/v1/models` (tên model), `curl -s http://localhost:8040/metrics | grep vllm:gpu_cache_usage_perc` (Prometheus cào endpoint này — `deploy/monitoring/prometheus.yml`), `curl -s http://localhost:8040/health`.

Cache trọng số nằm ở volume `hf_cache_vllm` (lần đầu tải ~6 GB AWQ hoặc ~18 GB bf16; máy thuê nên có ≥ 60 GB đĩa). `HF_TOKEN` chỉ cần cho repo gated (Qwen3.5 công khai).

## Đường CPU chính thức (D29) — profile `llama`

`models-cpu` chạy `ghcr.io/ggml-org/llama.cpp:server` với GGUF Q4_K_M của `planner_small` (`Qwen/Qwen3.5-2B`) từ `deploy/models/cache/<LLAMA_MODEL_FILE>` (gitignore; tải bằng `huggingface-cli download` hoặc xuất từ `make train`). Dùng cho máy dev Windows, demo dự phòng, kit hackathon và fallback chung kết. Khi bật profile này đặt `VLLM_BASE_URL=http://models-cpu:8040/v1` trong `.env`; `ctcv_agent` tự chọn `planner_small` khi `COMPOSE_PROFILES` chỉ có `cpu`.

```bash
docker compose -f deploy/docker-compose.yml --profile cpu --profile llama up -d
```

Máy dev không muốn chạy container llama.cpp: chạy `llama-server` ngay trên Windows và trỏ `VLLM_BASE_URL=http://host.docker.internal:8080/v1` (overlay dev đã khai `extra_hosts`).

## Kiểm tra nhanh trên máy GPU

```bash
make doctor GPU=1                  # SSH tới GPU_SSH_HOST: nvidia-smi, docker, /v1/models
docker compose -f deploy/docker-compose.yml --profile gpu pull models
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml --profile gpu up -d models
docker compose -f deploy/docker-compose.yml --profile gpu logs -f models   # chờ "Application startup complete"
```

Spike 2 giờ chốt D9 (AWQ + LoRA + ảnh cùng lúc trên 24 GB) ghi kết quả vào `docs/decisions/ADR-002-chon-model.md`; nếu vLLM chưa hỗ trợ tổ hợp này → `Qwen3.5-4B` bf16 làm cả hai vai (brief D9).
