# Báo cáo registry dữ liệu và mô hình

Sinh tự động bởi `python -m ctcv_data.pipeline registry` lúc 2026-09-25T07:56:09+00:00. Trạng thái: **HỢP LỆ**. Không sửa tay — sửa `datasets.yaml`/`models.yaml` rồi chạy lại.

## Bộ dữ liệu

| Tên | Phiên bản | Loại nguồn | Giấy phép | Phân phối lại | Dùng cho | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| guides-official | 0.1 | co_quan_nha_nuoc | Bản quyền cơ quan ban hành — chỉ truy xuất và trích dẫn, không phân phối lại (idea §7) | không | rag | match |
| tthc-bca-v1 | 1.0 | co_quan_nha_nuoc | Nguồn "Cổng Dịch vụ công - Bộ Công an" — ghi rõ nguồn khi sử dụng lại; chỉ truy xuất và trích dẫn | không | rag, eval | match |
| scenarios-v1 | 0.1 | synthetic | CC-BY-4.0 | có | sft, eval | match |
| coach-sft-v1 | 0.1 | synthetic | CC-BY-4.0 | có | sft | missing |
| coach-dpo-v1 | 0.1 | synthetic | CC-BY-4.0 | có | dpo | missing |
| ui-screens-v1 | 0.1 | synthetic | CC-BY-4.0 | có | ui, eval | match |
| drills-v1 | 0.1 | synthetic | CC-BY-4.0 | có | drill | match |
| eval-qa-v1 | 1.0 | synthetic | CC-BY-4.0 | có | eval | match |
| eval-dialogue-v1 | 0.1 | synthetic | CC-BY-4.0 | có | eval | missing |
| eval-redteam-v1 | 0.1 | synthetic | CC-BY-4.0 | có | eval | match |
| common-voice-vi | 17.0 | open_dataset | CC0-1.0 | có | eval | no_path |
| vivos | 1.0 | open_dataset | CC-BY-NC-SA-4.0 | không | eval | no_path |

## Mô hình

| Tên | Mô hình gốc | Giấy phép | Lượng tử hóa | Adapter |
| --- | --- | --- | --- | --- |
| planner-base | Qwen/Qwen3.5-9B | Apache-2.0 | none | — |
| planner-small-base | Qwen/Qwen3.5-2B | Apache-2.0 | none | — |
| vlm-base | Qwen/Qwen3.5-9B | Apache-2.0 | none | — |
| asr-phowhisper-small | vinai/PhoWhisper-small | BSD-3-Clause | int8 | — |
| asr-phowhisper-tiny | vinai/PhoWhisper-tiny | BSD-3-Clause | int8 | — |
| embed-bge-m3 | BAAI/bge-m3 | MIT | none | — |
| rerank-bge-reranker-v2-m3 | BAAI/bge-reranker-v2-m3 | MIT | none | — |
| ui-detector-yolox-tiny | yolox-tiny | Apache-2.0 | onnx | — |

## Kiểm tra sha256

| Tên | Đường dẫn | Tồn tại | Khai báo | Tính được | Kết quả |
| --- | --- | --- | --- | --- | --- |
| guides-official | data/raw/guides/manifest.jsonl | có | d71f674c0922 | d71f674c0922 | match |
| tthc-bca-v1 | data/raw/tthc/manifest.jsonl | có | e0e5229f2727 | e0e5229f2727 | match |
| scenarios-v1 | sandbox/scenarios | có | 0d6fb88d342c | 0d6fb88d342c | match |
| coach-sft-v1 | data/sft/train.jsonl | không | pending | — | missing |
| coach-dpo-v1 | data/dpo/pairs.jsonl | không | pending | — | missing |
| ui-screens-v1 | data/ui | có | a9d69e1485d2 | a9d69e1485d2 | match |
| drills-v1 | drills/scenarios | có | 794d5eeb4ae1 | 794d5eeb4ae1 | match |
| eval-qa-v1 | eval/sets/samples/qa_tthc.jsonl | có | 2f23e88d8891 | 2f23e88d8891 | match |
| eval-dialogue-v1 | eval/sets/samples/dialog.jsonl | không | pending | — | missing |
| eval-redteam-v1 | eval/redteam/scenarios.jsonl | có | a610b22d004c | a610b22d004c | match |

## Vấn đề

- Không có lỗi.

- CẢNH BÁO: datasets.yaml[coach-sft-v1]: chưa có file data/sft/train.jsonl
- CẢNH BÁO: datasets.yaml[coach-dpo-v1]: chưa có file data/dpo/pairs.jsonl
- CẢNH BÁO: datasets.yaml[eval-dialogue-v1]: chưa có file eval/sets/samples/dialog.jsonl
