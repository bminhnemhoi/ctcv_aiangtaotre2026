# training/ — runbook huấn luyện (gói `ctcv-training`, import `ctcv_training`)

Runbook `make train` theo plan §7: SFT → DPO → lượng tử hóa → YOLOX → (ASR LoRA tùy chọn), chạy
trên 1 GPU 24 GB (~8–10 giờ tổng). E01 giao phần không cần GPU: cấu hình có schema, cổng ngân
sách và quy ước thư mục run. Trình huấn luyện thật ở E07 (planner) và E08 (YOLOX); tới lúc đó
`make train` in `CHƯA HIỆN THỰC — E07` và thoát 0.

## Lệnh

```bash
uv run pytest training -q                                  # test cấu hình, ngân sách, run dir
uv run python -m ctcv_training.budget --hours 3            # kiểm tra 1 job 3 giờ GPU (exit 0/1)
uv run python -m ctcv_training.budget --hours 3 --api-vnd 200000 --json
uv run python -m ctcv_training.budget --record --hours 2.5 --name planner-sft   # ghi chi tiêu thật
make train                                                 # E07+: chạy đủ bảng dưới; E01: CHƯA HIỆN THỰC
```

Mã thoát của `budget`: 0 = trong hạn mức, 1 = vượt hạn mức (dừng và hỏi người dùng — plan §6),
2 = tham số/file sai.

## Bảng `make train` (plan §7) và file cấu hình

| Bước | File | Mặc định | Thời gian | Điều kiện dừng |
| --- | --- | --- | --- | --- |
| SFT LoRA planner | `configs/sft.yaml` | `planner` (Qwen3.5-9B), r=16, alpha=32, lr 1e-4, 3 epoch, seq 4k, bf16, gradient checkpointing | ~3 giờ | Loss eval không giảm 2 lần liên tiếp |
| DPO | `configs/dpo.yaml` | 2.000 cặp, beta 0,1, 1 epoch | ~1 giờ | Reward margin ≥ 0,5 |
| Lượng tử hóa | `configs/quantize.yaml` | AWQ 4-bit (vLLM) cho `planner`; GGUF Q4_K_M (llama.cpp) cho `planner_small` = Qwen3.5-2B (D8/D29) | ~1 giờ | Eval giảm ≤ 2 điểm so với FP16 |
| YOLOX-Tiny UI | `configs/yolox.yaml` | 20.000 ảnh, 50 epoch, xuất ONNX (Apache-2.0 — D7) | ~2 giờ | mAP50 ≥ 0,85 |
| ASR LoRA (tùy chọn) | `configs/asr_lora.yaml` | PhoWhisper-small, 5–10 giờ audio pilot **có đồng thuận** | ~1 giờ | WER giọng địa phương giảm ≥ 3 điểm |

Quy ước trong mọi file: `model_key` trỏ tới khóa trong `config/models.yaml` (không ghi tên model
trực tiếp), `dataset` trỏ tới tên trong `data/registry/datasets.yaml`, `budget.estimated_gpu_hours`
≤ 20 và `estimated_api_vnd` ≤ 500.000 (schema ép). Schema: `configs/schema.json`
(`ctcv_training.configs.load_training_config("sft")` nạp + kiểm).

## Ngân sách (`budget.json`, hook `.claude/hooks/budget.py`)

Hạn mức plan §4: 300 giờ GPU tổng, ≤ 20 giờ/job; API sinh dữ liệu ≤ 2.000.000 đ tổng, ≤ 500.000 đ
mỗi tác vụ. `ctcv_training.budget.check(job_estimate_hours, api_vnd)` trả `Decision{allowed,
reasons, gpu_hours_remaining, api_vnd_remaining}`; file lỗi/thiếu ⇒ chặn (fail-closed). Module chỉ
dùng thư viện chuẩn nên hook Claude Code nhập được ngoài virtualenv. `api_total_limit_vnd` là bí danh
của `api_budget_vnd` cho hook; hai giá trị phải bằng nhau. Trước khi chạy job: cập nhật
`next_job` (hook `guard` đọc), sau khi xong: `--record` để cộng vào `spent`.

## Thư mục run (`runs/<YYYY-MM-DD>-<tên>/`, gitignore)

`ctcv_training.runs.create_run(name, config)` tạo `config.yaml` (bản sao cấu hình đã dùng),
`metrics.json` (`status`: created → running → finished|failed, `metrics{}`) và `MODEL_CARD.md`
(mẫu tiếng Việt, các mục **[điền]** do trình huấn luyện điền). Không ghi đè run đã có. Checkpoint
được chọn khai vào `data/registry/models.yaml` (`adapter_path`, `quantization`, `eval_report`,
`card`) — không sửa mục model gốc. `reports/ablation.md` (E07) so sánh base / SFT / SFT+DPO,
có/không xác nhận ý định, có/không trích dẫn, VLM đơn vs YOLOX+VLM, 9B máy chủ vs 2B tại chỗ;
`make dossier` nhúng thẳng.

## Không được làm

Train khi `make doctor GPU=1` chưa xanh; vượt hạn mức mà không hỏi; train trên GPU đang phục vụ
pilot; đổi model đang phục vụ khi eval dưới ngưỡng chặn; dùng dữ liệu pilot thật (chỉ tổng hợp
hoặc audio có đồng thuận riêng); commit checkpoint (`*.safetensors`, `*.gguf`, `*.onnx` gitignore).
