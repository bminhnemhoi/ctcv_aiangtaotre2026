# data/ — pipeline dữ liệu và registry (gói `ctcv-data`, import `ctcv_data`)

Toàn bộ dữ liệu của CTCV do pipeline tự lấy từ nguồn công khai hoặc tự sinh (idea §7); người
dùng chỉ duyệt mẫu gắn cờ. Mọi tập có bản kê nguồn gốc, giấy phép và mã băm để đưa vào bản kê
khai của BTC (`make declaration` đọc `data/registry/*.yaml`).

## Lệnh

```bash
python -m ctcv_data.pipeline --list            # 10 bước và epic hiện thực
python -m ctcv_data.pipeline crawl             # dry run offline: kiểm sources.yaml, ghi manifest skeleton
python -m ctcv_data.pipeline crawl --online    # thêm: robots.txt mỗi tên miền + crawl thật trang TTHC Bộ Công an (ADR-007)
python -m ctcv_data.pipeline normalize         # offline: trang TTHC thô → data/clean/tthc/records/*.json + báo cáo
python -m ctcv_data.pipeline registry          # kiểm schema + sha256 → data/registry/REPORT.md
python -m ctcv_data.pipeline registry --update-hashes   # điền sha256 cho mục đang 'pending'
python -m ctcv_data.pipeline                   # = make data: chạy 10 bước theo thứ tự plan §7
uv run pytest data -q                          # test
```

Mã thoát: 0 = mọi bước ok hoặc "CHƯA HIỆN THỰC — E0X"; 1 = một bước lỗi (ví dụ registry sai schema).

## Các bước (plan §7) và trạng thái

| Bước | Module | Epic | E01 |
| --- | --- | --- | --- |
| 1. Crawl | `pipeline/crawl.py` | E03 | dry run + manifest skeleton; `--online`: crawl TTHC (ADR-007) |
| 2. Chuẩn hóa | `pipeline/normalize.py` | E03 | TTHC → bản ghi v1 (ADR-007 C2) |
| 3. Chunk + embed | `pipeline/chunk_embed.py` | E03 | chưa |
| 4. Sinh kịch bản | `pipeline/synth_scenarios.py` | E06 | chưa |
| 5. Render ảnh | `pipeline/render_ui.py` | E08 | chưa |
| 6. Sinh hội thoại | `pipeline/synth_dialogues.py` | E06 | chưa |
| 7. Lọc + LLM-judge | `pipeline/filter_judge.py` | E06 | chưa |
| 8. Kịch bản lừa đảo | `pipeline/synth_drills.py` | E09 | chưa |
| 9. Tập đánh giá | `pipeline/build_eval_sets.py` | E06 | chưa |
| 10. Registry | `pipeline/registry.py` | E01 | thật |

Mỗi bước là một module có `run(cfg: PipelineConfig) -> StepReport`; bước chưa hiện thực trả
`StepReport.not_implemented` (in "CHƯA HIỆN THỰC — E0X", exit 0).

## Nguồn crawl — `data/sources.yaml`

- Chỉ crawl tên miền trong `allowlist`; URL ngoài danh sách bị từ chối ngay khi nạp file.
- Quy tắc: 1 yêu cầu/giây, tôn trọng `robots.txt`, chỉ trang hướng dẫn công khai
  (`guide_path_hints`), không đăng nhập, không trang quảng cáo.
- Nội dung hướng dẫn **chỉ để truy xuất và trích dẫn, không phân phối lại**; snapshot HTML nằm
  ngoài repo (`data/raw`, gitignore), registry ghi sha256 của manifest.
- Tên miền `status: can_xac_nhan` (khonggianmang.vn, chongluadao.vn, vbpl.vn, 3 ngân hàng ví dụ)
  phải được đội kiểm ToS và ghi `tos_checked_on` trước khi crawl ở E03.

## Thủ tục hành chính — Cổng DVC Bộ Công an (ADR-007)

- Nguồn: 9 trang danh sách `dichvucong.bocongan.gov.vn/bocongan/bothutuc?linh_vuc=<MÃ>&per_page=50`
  trong `data/sources.yaml` (mục **đề xuất, chờ người dùng duyệt**; `tos_checked_on: null` — chân
  trang chỉ ghi "Khi sử dụng lại thông tin, đề nghị ghi rõ nguồn "Cổng Dịch vụ công - Bộ Công an"",
  cần một thành viên là người xác nhận ToS).
- `crawl --online`: đọc robots.txt 1 lần mỗi host (5xx/timeout = cấm cả host, RFC 9309), tải trang
  danh sách rồi các trang `tthc?matt=`; **một bộ giới hạn nhịp dùng chung** — giữa hai yêu cầu bất kỳ
  cách nhau ≥ `crawl_rules.min_interval_s` (1,2 s); User-Agent và timeout lấy từ `sources.yaml`;
  chỉ tải host https trong allowlist (kể cả khi bị chuyển hướng). Không đổi User-Agent để né chặn.
- Đầu ra (gitignore): `data/raw/tthc/bca/{list_<MÃ>,tthc_<matt>}.html` và
  `data/raw/tthc/manifest.jsonl` — mỗi lần tải một dòng: `url, kind (listing|detail), matt,
  linh_vuc_code, name, fetched_at (UTC, Z, mili giây), http_status, bytes, sha256_raw, path,
  robots_allowed, user_agent`. Trang có hash khác lần crawl trước được liệt kê ở `hash_changed`.
- `normalize` (offline, `ctcv_data.tthc_bca`, chỉ dùng stdlib): parse → bản ghi TTHC v1 → kiểm
  `config/schemas/tthc-record.schema.json` → `data/clean/tthc/records/<procedure_id>.json`;
  `procedure_id` trùng thì giữ trang đầu và cảnh báo. `data/clean/tthc/normalize_report.json` ghi số
  trang/bản ghi, lỗi schema, cảnh báo, độ phủ (%), phân bố lĩnh vực, khoảng cách nhỏ nhất giữa hai
  yêu cầu (tính từ `fetched_at`).
- Nguyên tắc không bịa: `updated_at`, `effective_date` luôn `null` (cổng không công bố); mục phí chỉ
  có số trần hoặc chữ lạ (ví dụ "1", "Công an Xã") → `phi_le_phi: null`, cảnh báo `phi_khong_ro`;
  mức phí > 10 triệu đồng → cảnh báo `phi_bat_thuong` để người kiểm tra nguồn. `phi_vnd` chỉ lấy số
  có đơn vị đồng/đ/VNĐ (USD không quy đổi). Bảng "Lưu ý" trong thành phần hồ sơ không tính là giấy tờ.
- Registry: mục `tthc-bca-v1` (`redistribute: false`, sha256 của `manifest.jsonl`).

## Manifest — `data/raw/guides/manifest.jsonl`

Mỗi dòng một JSON (`ctcv_data.manifest.ManifestEntry`): `url`, `agency`, `source_type`,
`license_note`, `status` (pending|fetched|skipped|error), `fetched_at`, `sha256`,
`content_path`, `robots`, `notes`. Đọc/ghi bằng `read_manifest` / `write_manifest`; bước chuẩn
hóa cảnh báo khi `sha256` đổi so với lần trước.

## Registry — `data/registry/datasets.yaml`, `models.yaml`

Schema ở `config/schemas/datasets-registry.schema.json` và `models-registry.schema.json`
(gói này sở hữu ngữ nghĩa registry). Mỗi bộ dữ liệu bắt buộc có: `source_type`
(qppl | co_quan_nha_nuoc | ngan_hang | synthetic | open_dataset), `redistribute`, `derived_from`,
`tos_checked_on`, `sha256` (hoặc `pending`), `path`; tập tổng hợp thêm `generator_model`,
`generator_license`, `tos_url`. Mỗi mô hình có `license` (SPDX), `license_url`, `card`.
Ràng buộc: giấy phép NC (VIVOS CC BY-NC-SA 4.0) ⇒ `eval_only: true`, `redistribute: false`,
chỉ dùng cho `eval`. PhoWhisper là BSD-3-Clause (D10), YOLOX-Tiny Apache-2.0 (D7).

`REPORT.md` được sinh mỗi lần chạy bước registry; không sửa tay.

## Thư mục dữ liệu (gitignore, giữ `.gitkeep`)

`raw/` (HTML/PDF gốc + manifest), `clean/` (Markdown đã chuẩn hóa), `ui/` (ảnh + nhãn DOM),
`sft/` (`train.jsonl`), `dpo/` (`pairs.jsonl`). Không bao giờ commit dữ liệu pilot hay dữ liệu
người dùng thật vào đây (D21).
