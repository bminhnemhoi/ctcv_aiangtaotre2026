# `docs/dossier/build/` — sinh Tài liệu dự án (MẪU 3, Bảng C) từ Markdown

## Chạy

```bash
uv run python docs/dossier/build/build_dossier.py --draft            # bản nháp (mặc định ra docs/dossier/out)
uv run python docs/dossier/build/build_dossier.py                    # bản chính thức: mọi cổng phải qua
uv run python docs/dossier/build/build_dossier.py --draft --out /tmp/x --no-pdf
make dossier DRAFT=1        # tương đương --draft (Makefile của WP F)
uv run pytest docs/dossier/build/tests -q
```

Tùy chọn: `--template` (mẫu BTC), `--src` (thư mục 13 file), `--figures` (PNG/MMD), `--team`, `--team-example`,
`--legal-refs`, `--eval-report`, `--no-pdf`. Mã thoát: `0` thành công, `2` lỗi kiểm tra (in `LỖI: …` ra stderr).

## Script làm gì

1. Mở `docs/template/AI2026_Mau_ho_so.docx`, **xóa phần MẪU 1 (Bảng A) và MẪU 2 (Bảng B)**, giữ từ tiêu đề
   "MẪU HỒ SƠ DỰ ÁN DỰ THI BẢNG C" đến khối ký.
2. Điền bảng thông tin đội (22 dòng × 4 cột) từ `docs/dossier/private/team.yaml`; thiếu file → `--draft` dùng
   `team.example.yaml` và in dấu đỏ "BẢN NHÁP — DỮ LIỆU MẪU" ở đầu trang và header; chế độ chính thức dừng.
   Thêm dòng "Tên sản phẩm: …" dưới tiêu đề (mẫu không có ô này).
3. Với mỗi mục 1–13: tìm tiêu đề trong mẫu, kiểm tra H1 của `src/NN-*.md` **nguyên văn** bằng tiêu đề, giữ đoạn
   "Nội dung trình bày" của mẫu (blockquote cùng nội dung trong file `.md` bị bỏ qua khi render), xóa các dòng
   "........" và chèn nội dung đã render (`md2docx.py`: tiêu đề phụ, đoạn, danh sách, bảng, đậm/nghiêng/mã, hình).
4. Thay `{{eval:<khóa>}}` bằng giá trị trong `eval/reports/latest.json` (tra theo khóa chấm `qa.citation_support`,
   rồi `metrics[...]`, rồi khóa phẳng); thiếu → `⟪CHƯA ĐO⟫` (nền vàng, chữ đỏ). Thay `{{team:<khóa>}}` bằng
   `lien_ket.<khóa>` hoặc khóa gốc trong `team.yaml`; giá trị còn `<...>` → `⟪CHƯA CÓ: team.<khóa>⟫`.
5. Quét mọi số hiệu văn bản pháp luật (`134/2025/QH15`, `142/2026/NĐ-CP`, `05/2026/TT-BKHCN`, …) và đối chiếu
   `docs/legal/refs.yaml`: số hiệu chưa có `verified_on` → cảnh báo (nháp) hoặc dừng (chính thức) — LEG-11.
6. Ghi `docs/dossier/out/01_TaiLieuDuAn_CTCV.docx` + `dossier-report.json`; gọi `soffice --headless --convert-to pdf`
   nếu tìm thấy LibreOffice (PATH hoặc `C:\Program Files\LibreOffice`), nếu không in đúng lệnh để chạy tay.
7. In bảng số từ theo mục so với ngân sách, ước tính số trang (`tổng từ / 450 + 1` trang thông tin đội), số dấu
   chưa giải quyết, số hiệu văn bản đã/chưa xác minh.

## Định dạng `eval/reports/latest.json`

Object JSON lồng nhau theo khóa chấm dùng trong `src/*.md`; số thực được in với dấu phẩy thập phân, `true/false`
thành "Đạt"/"Không đạt". Ví dụ tối thiểu:

```json
{
  "meta": {"report_date": "2026-09-28", "git_tag": "v1.0-dossier"},
  "rag": {"recall_at_5": 0.93, "recall_at_5_pass": true},
  "qa": {"citation_support": 96.5, "citation_support_pass": true, "hallucination": 2.1, "hallucination_pass": true},
  "dialogue": {"max_two_sentences": 100, "has_concrete_action": 98.7, "first_turn_intent_confirmation": 100, "pass": true},
  "redteam": {"size": 50, "leaks": 0, "real_actions": 0, "pass": true},
  "audio": {"wer_standard": 11.2, "wer_regional": 17.8, "wer_elderly": 19.4, "pass": true},
  "tts": {"rtf": 0.21, "mos": 3.7, "pass": true},
  "latency": {"sandbox_p95_s": 0.6, "coach_p95_s": 3.4, "ttfa_s": 1.2, "pass": true},
  "loadtest": {"error_rate": 0.4, "error_rate_pass": true},
  "ops": {"uptime_pct": 99.6, "uptime_pass": true},
  "sandbox": {"scenario_count": 6}, "drills": {"count": 10},
  "pilot": {"dates": "26–27/9/2026", "n": 8, "mean_age": 61, "regions": "Nam, Trung", "self_completion_rate": 62.5,
            "time_first_s": 210, "time_second_s": 120, "time_reduction_pct": 43, "vuln_before": 58, "vuln_after": 31,
            "sus": 71, "asr_retry_pct": 14, "quote_1": "\"Nó nói ngắn, tôi làm theo được\" (nữ, 63 tuổi)"},
  "baseline": {"max_two_sentences": 12, "has_concrete_action": 35, "first_turn_intent_confirmation": 4,
               "citation_support": 21, "hallucination": 18, "redteam_leaks": 9, "redteam_real_actions": 6},
  "ablation": {"no_rag": {"citation_support": 23, "hallucination": 17}, "no_guardrail": {"leaks": 7},
               "no_intent": {"mistakes_delta": "+1,8 bước sai/phiên"}, "no_verify": {"citation_support": 88},
               "small_model": {"summary": "≤ 2 câu 91%, hallucination 4,1%, p95 5,2 s"}}
}
```

Các giá trị trên chỉ là ví dụ định dạng, **không phải số đo**. Chỉ `make eval`/`make pilot-report` được ghi file này.

## `docs/legal/refs.yaml` (sở hữu bởi gói B; script chấp nhận schema linh hoạt)

```yaml
refs:
  - so_hieu: 134/2025/QH15
    ten: Luật Trí tuệ nhân tạo
    ngay_hieu_luc: "2026-03-01"
    dieu_khoan: "Điều …"
    url: https://vbpl.vn/...
    verified_on: "2026-09-18"
    verified_by: "<tên thành viên>"
```

Script đọc danh sách ở khóa `refs`/`documents`/`van_ban`/`items` (hoặc danh sách gốc), lấy số hiệu từ
`so_hieu`/`number`/`id`, và coi mục có `verified_on` không rỗng là đã xác minh.

## Hình

`![Hình 1. …](figures/04-pipeline-du-lieu.png)` chèn ảnh (rộng 15,5 cm) khi file tồn tại trong `docs/dossier/src/`
hoặc `docs/dossier/figures/`; thiếu → `⟪HÌNH CHƯA CÓ: …⟫`. Khối ```` ```mermaid ```` đứng ngay trước dòng ảnh được
xuất thành `figures/<tên>.mmd`; render bằng `npx -y @mermaid-js/mermaid-cli -i docs/dossier/figures/<tên>.mmd
-o docs/dossier/figures/<tên>.png -w 1600 -b white` (xem `docs/dossier/figures/README.md`).

## Kiểm thử

`docs/dossier/build/tests/test_build.py` chạy trên mẫu thật: 13 tiêu đề đúng thứ tự, không còn "Bảng A/B", dòng
chấm đã thay, dấu `⟪CHƯA ĐO⟫` được báo cáo, bảng đội điền từ file mẫu (kèm dấu DỮ LIỆU MẪU) và từ file thật, thay
số từ `latest.json`, chế độ chính thức dừng khi thiếu `team.yaml`/còn dấu/còn số hiệu chưa xác minh, ngân sách từ.

## Hồ sơ Data for Life 2026 — `build_dfl.py`

`uv run python docs/dossier/build/build_dfl.py [--draft] [--no-pdf] [--env <file>]` dựng
`docs/dossier/out/dfl/de-xuat-giai-phap.{docx,pdf}` từ `docs/dossier/dfl/` (hướng dẫn: `docs/dossier/dfl/README.md`).

- Nguồn số: `eval/reports/latest.json` (gốc), `ablation-tthc.json` dưới `ablation.*`, `env-tthc.json` (mặc định
  cạnh `--eval`) dưới `env.*`. Ngoài khóa gốc (`env.machine.cpu`, `env.ollama.models.1.quantization` — chỉ số
  danh sách tính từ 0), có bí danh chép nguyên giá trị: `env.cpu`, `env.cpu_count`, `env.ram_gb`, `env.gpu`,
  `env.commit`, `env.code_sha256`, `env.model.<slug>.*` (`qwen3.5:2b` → `env.model.qwen3_5_2b.quantization`,
  gộp cả `gpu_offload_pct` lúc đo). Thiếu file hoặc khóa → giữ giá trị dự phòng, không bịa số.
- Định dạng số (dùng chung với `build_dossier.py`): dấu phẩy thập phân, làm tròn half-up 2 chữ số; khóa kết thúc
  bằng `_s` hoặc chứa `latency` giữ 3 chữ số (0,145 s; 2,219 s); bỏ số 0 thừa (100,0 → 100).
- Tiêu đề: H1 của `de-xuat-giai-phap.md` được in thành tiêu đề giữa trang (15 pt, đậm). Nếu dòng ngay sau H1 là
  một dòng in đậm tự soạn (`**…**`), H1 bị bỏ để không in tiêu đề hai lần; `build-report.json` ghi `"title"`:
  `h1` | `in_dam_co_san` | `khong_co`. Thư cam kết (`cam-ket.md`, chỉ để dán vào form) không in H1.
- Kiểm tra: ≤ 10 trang, ≤ 10 MB, không còn `{{…}}`/`⟪…⟫`, giới hạn ký tự các ô của `mo-ta-ngan.md`; bản chính
  thức thoát mã 1 khi vi phạm. Test: `docs/dossier/build/tests/test_build_dfl.py`.
