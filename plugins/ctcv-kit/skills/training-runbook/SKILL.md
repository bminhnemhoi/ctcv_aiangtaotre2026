---
name: training-runbook
description: Runbook huấn luyện make train của CTCV (plan §7) — LoRA SFT, DPO, lượng tử hóa AWQ/GGUF, YOLOX-Tiny, ASR LoRA tùy chọn; ngân sách GPU/API, cấu trúc training/runs, model card, ablation, registry models.yaml. Use when working under training/ or choosing a checkpoint to serve.
---
# `make train` — runbook (plan §7; mã ở `training/src/ctcv_training/`, config ở `training/configs/*.yaml`)

## Điều kiện tiên quyết
- Máy GPU thuê (1 × 24 GB) qua SSH: `make doctor GPU=1` xanh; máy dev Windows **không** chạy train.
- `make data` đã xong: `data/sft/train.jsonl`, `data/dpo/pairs.jsonl`, `data/ui/`, registry có sha256.
- **Ngân sách** (`training/budget.json`, hook `guard` → `budget.py` chặn `make train|data|finetune`, `uv run -m ctcv_training`, `uv run python training/…`): cập nhật `next_job{name, estimated_gpu_hours, estimated_api_vnd}` **trước** khi chạy; > 20 giờ GPU/job hoặc > 500.000 đ API/tác vụ, hoặc tổng > 300 giờ / 2.000.000 đ → hook chặn = điểm dừng bắt buộc, hỏi người dùng. Sau run: cộng vào `spent`.

## Các bước (cấu hình mặc định; mỗi bước có `training/configs/<bước>.yaml`, không hard-code)
| Bước | Cấu hình | Thời gian | Điều kiện dừng / chấp nhận |
| --- | --- | --- | --- |
| SFT LoRA planner | base `config/models.yaml: planner` (Qwen3.5-9B), r=16, alpha=32, lr 1e-4, 3 epoch, seq 4k, bf16, gradient checkpointing | ~3 giờ | Loss eval không giảm 2 lần liên tiếp |
| DPO | 2.000 cặp, beta 0,1, 1 epoch | ~1 giờ | Reward margin ≥ 0,5 |
| Lượng tử hóa | AWQ 4-bit cho vLLM (9B); GGUF Q4_K_M cho `planner_small` Qwen3.5-2B (đường CPU D29 — không phải APK) | ~1 giờ | Eval giảm ≤ 2 điểm so với FP16 |
| YOLOX-Tiny UI | 20.000 ảnh, 50 epoch, ONNX export (Apache-2.0; **cấm Ultralytics/YOLOv5** — D7) | ~2 giờ | mAP50 ≥ 0,85 |
| ASR LoRA (tùy chọn, Pha D) | PhoWhisper-small, 5–10 giờ audio pilot có đồng thuận riêng | ~1 giờ | WER giọng địa phương giảm ≥ 3 điểm |

D9 (đề xuất, chờ người dùng): một model Qwen3.5-9B phục vụ cả planner (LoRA) lẫn đọc ảnh (base, multi-LoRA vLLM); spike 2 giờ AWQ + LoRA + vision là điều kiện chốt; không đạt → Qwen3.5-4B bf16 làm cả hai (ADR-002).

## Cấu trúc run
`training/runs/{YYYY-MM-DD}-{name}/` (gitignore) gồm `config.yaml` (bản đã dùng), `log.jsonl`, `metrics.json`, `checkpoint/`, `MODEL_CARD.md` tự sinh (base, dữ liệu + sha256, giấy phép, siêu tham số, chỉ số, hạn chế, ngày). `training/reports/` (commit): `ablation.md`, tóm tắt run.

## Sau huấn luyện
1. `make eval` (quick trên máy GPU) cho checkpoint; so `config/eval.yaml` (accept/block). **Dưới ngưỡng chặn 2 lần → quay về base + prompt cấu trúc, ghi ablation trung thực; không đổi model đang phục vụ.**
2. Ghi `data/registry/models.yaml[]`: `name`, `base`, `license`, `license_url`, `adapter_path`, `quantization`, `eval_report`, `served_at`, `card`.
3. Cập nhật `training/reports/ablation.md`: base / SFT / SFT+DPO / có–không xác nhận ý định / có–không trích dẫn / VLM đơn vs YOLOX+VLM / 9B vs 2B; bản 29/9 dùng **ablation thành phần** (RAG/guardrail/xác nhận ý định bật–tắt trên base) thay cho ablation fine-tune (ADR-006).
4. Checkpoint được chọn → `config/models.yaml` chỉ đổi qua ADR (đổi model = điểm dừng); deploy qua `devops`.

## Cấm
Chạy khi chưa cập nhật `budget.json` · dữ liệu có PII hoặc CC-NC/GPL cho bản phát hành · nới `config/eval.yaml` · bỏ test/skip để xanh · ghi "tự huấn luyện" cho phần dùng API thương mại · lưu checkpoint/`*.safetensors`/`*.gguf` vào git.
