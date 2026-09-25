# DAILY — Nhật ký trạng thái hằng ngày (plan §11 KPI; cập nhật bởi `/daily`, hook `daily.py` và `make daily`)

Quy ước: một mục `## YYYY-MM-DD` mỗi ngày, mới nhất ở trên; so tiến độ với **ADR-006** (lịch 3 pha, ngày dương) — không so với D-day của plan §6 (đã lệch, xem errata plan.md). Số liệu chỉ ghi khi có nguồn (`docs/status/last_check.json`, `eval/reports/*`, hóa đơn GPU). Mục "Phiên gần nhất" do hook `daily.py` (Stop) ghi đè; không sửa tay mục đó.

## Phiên gần nhất
- Thời điểm (UTC): 2026-09-25T15:49:22+00:00 · session_id: 42a8ed58-aeab-497e-9a6e-2b46adf26261
- Nhánh: nogit · HEAD: nogit
- Thay đổi mã chưa qua make check: CÓ (5 file; make check gần nhất: 2026-09-18T01:30:31+00:00)

## Mẫu một ngày (sao chép khi thêm ngày mới)

```
## YYYY-MM-DD (Thứ …) — Pha … / mốc ADR-006: …
| KPI | Giá trị | Nguồn |
| --- | --- | --- |
| Epic đang làm và % test xanh | E0X — …% | last_check.json, pytest |
| Số test / e2e | … unit, … integration, … e2e | make check |
| Eval quick gần nhất | qa …, dialogue …, vision …, audio …, redteam …, load … (hoặc "chưa có GPU") | eval/reports/<ngày>.md |
| Số lỗi red-team | … / … kịch bản | make redteam |
| Độ trễ p95 staging | sandbox … s, hỏi đáp … s, TTFA … s | make loadtest / log |
| Chi phí GPU/API lũy kế | … giờ GPU / 300; … đ API / 2.000.000 | training/budget.json, hóa đơn |
| Câu hỏi đang chờ người dùng | … (liệt kê) | epic §Câu hỏi mở, ADR |
| Rủi ro mới | … | — |
Sớm/trễ so với ADR-006: … ngày. Việc hôm nay: … Việc người dùng hôm nay: …
```

---

## 2026-09-25 (Thứ Sáu) — Chuyển sang Data for Life 2026 (ADR-007)

**Quyết định.** Người dùng bỏ cuộc thi Sáng tạo trẻ AI (Bảng C) và dự thi Data for Life mùa 4 (Bộ Công an), đề
DA940-01. Hạn vòng 1 trên form là 25/09/2026, không ghi giờ; kế hoạch là nộp trước 12:00. ADR-007 (đề xuất — chờ người
dùng duyệt) và phụ lục `ADR-007-hop-dong.md`; ADR-006 ghi "thay thế bởi ADR-007"; ADR-008 (đề xuất) trình bày lịch vòng
2–4 và phương án cho ba lỗi nền của cổng audit. Orchestrator tạm quyết khi người dùng chưa trả lời: crawl khoảng 110
thủ tục (mục tiêu) trên 9 trang danh sách của Cổng Dịch vụ công Bộ Công an, `tos_checked_on` để trống chờ một thành
viên xác nhận; mục mới trong `data/sources.yaml` là đề xuất; không sửa CLAUDE.md, allowed-deps hay cấu hình audit.

| KPI | Giá trị | Nguồn |
| --- | --- | --- |
| Epic đang làm | Kế hoạch thi công DFL (18 gói); P7a tài liệu xong | kế hoạch orchestrator 25/9 |
| Eval qa (recall@5, citation_support, p95) | chưa đo | `eval/reports/latest.json` (bản 19/9 chưa có suite qa thủ tục) |
| make check gần nhất | 2026-09-18T01:30:31Z (QUICK=1, ok); chưa chạy lại sau các thay đổi DFL | `docs/status/last_check.json` |
| Câu hỏi đang chờ người dùng | duyệt ADR-007; sửa 2 dòng CLAUDE.md; ba lỗi nền audit (ADR-008); xác nhận ToS nguồn; duyệt mục mới `data/sources.yaml`; commit đầu tiên | `docs/dossier/dfl/checklist-nop.md` |

**Bốn sóng việc** (giờ dự kiến theo kế hoạch orchestrator, tính từ 02:15):
1. Sóng 0: P0 môi trường, P2a hợp đồng mã, P7a tài liệu, P5 giao diện web.
2. Sóng 1 (sau P2a): P1 dữ liệu, P2b chỉ mục, P3 bộ trả lời, P4 API.
3. Sóng 2: P7b bản đề xuất, P10 công cụ PDF và video, P6 eval, P8 câu hỏi thực tế, P9 tích hợp.
4. Sóng 3: P11 bảo mật → chủ gói sửa lỗi → P12 cổng QA cùng P13 quay demo → P14 chạy eval trên máy rảnh → P7c chốt PDF
   cùng ghép video. Hợp nhất theo thứ tự backend → frontend → data.

**Rủi ro.** Hạn nộp mơ hồ (nộp trước 12:00). Độ trễ CPU của `qwen3.5:2b` (dự phòng `CTCV_RAG_COMPOSE_MODE=template_only`,
vẫn báo số cả hai chế độ, tua nhanh phải ghi rõ). Model nhỏ bịa hoặc chèn chữ Hán (lớp kiểm chứng chặn). Repo chưa có
commit, nhiều gói sửa cùng cây thư mục. Chỉ phủ thủ tục của Bộ Công an; chưa có ngày hiệu lực. Đánh giá vòng tròn vì câu
hỏi sinh từ chính bản ghi (trộn câu soạn tay, tách dev/test). Cổng audit còn đỏ vì ba lỗi nền. Thể lệ Điều 7 và 13: chỉ
trình bày phần chạy thật, số chỉ lấy từ `eval/reports/`. ADR-007 dài hơn 1 trang (chép nguyên văn nội dung architect).

**Việc người dùng hôm nay:** theo `docs/dossier/dfl/checklist-nop.md`: trả lời 3 câu hỏi mở; commit đầu tiên; tạo hồ sơ
trên dataforlife.vn, đội từ 3 người, đội trưởng đủ 18 tuổi có link GitHub hoặc portfolio; tạo
`docs/dossier/private/team-dfl.yaml`; duyệt PDF và video lúc khoảng 08:00; tải video ở chế độ ai có link đều xem được;
chọn DA940-01; mọi thành viên gõ chữ ký; xem /preview; **gửi hồ sơ trước 12:00**; lưu ảnh xác nhận.

### Cập nhật 10:30 — số đo thật và hồ sơ v1 (P14, P13, P7c)

| KPI | Giá trị | Nguồn |
| --- | --- | --- |
| Kho thủ tục | 107 thủ tục (98,17 % của 109 trang), 955 đoạn, 8 lĩnh vực; phí dạng số 10,3 %, thành phần hồ sơ 81,3 %; 22 bản ghi gắn cờ | `latest.json` → `suites.qa.details.kb` |
| Tập đánh giá | 75 câu dev, 138 câu test | `suites.qa.details.split_sizes` |
| recall@5 / answer_accuracy / chỉ phần chữ | 95,65 % / 84,35 % / 68,7 % | `suites.qa.metrics` |
| citation_support / hallucination | 98,08 % (ĐẠT ≥ 95) / 1,92 % (ĐẠT ≤ 3) | `suites.qa.metrics`, `rows[].verdict` |
| numeric_fidelity / refusal_accuracy / false_escalation_rate | 100 % / 91,3 % / 11,3 % | `suites.qa.metrics` |
| Độ trễ p50 / p95 | 1,284 s / 2,219 s, **có GPU hỗ trợ** (RTX 4050 Laptop, Ollama 100 % GPU) | `suites.qa.metrics`, `env-tthc.json` |
| Ablation `llm_unverified` → `llm_verified` | hallucination 12,5 % → 1,92 %; câu mô hình giữ lại 68,27 % của 104 | `ablation-tthc.json` |
| Red-team | 50/50 qua, 0 rò rỉ, 0 hành động thật | `suites.redteam.metrics` |
| Kết nối mạng khi đo | chỉ `localhost:11434` | `suites.qa.details.network_hosts` |
| Cổng QA | Trước lượt đo: `uv run pytest services/agent eval data` xanh (báo cáo P14). Lúc 07:55 toàn bộ Python chỉ đỏ 2 test (`test_rag_index.py::test_embedder_failure_degrades_to_bm25`, `test_check_deps.py::test_real_repo_lockfile_is_fully_allowed` — điểm dừng người dùng). `make check` chưa chạy lại từ 18/9 | báo cáo orchestrator; `docs/status/last_check.json` |
| Hồ sơ | PDF 9 trang, 538.719 byte, không còn placeholder (bản nộp, không `--draft`) | `docs/dossier/out/dfl/build-report.json` |
| Video | Chưa có: bước `can-bo-tim` đỏ vì màn cán bộ không gọi lại API khi chọn trường hợp (thuộc P5) | `kich-ban-video.md` mục Trạng thái v1 |

Sửa trong hồ sơ: bỏ mọi chỗ ghi "CPU, không GPU" (lượt đo có GPU); bỏ Hình 4 màn cán bộ (chưa chụp được); thêm vào
"Chưa đạt": lỗi màn cán bộ, câu không dấu 9/17, khẩu ngữ 12/18, phương ngữ 5/8 (`suites.qa.details.per_kind`).

**Việc người dùng còn lại** (thứ tự trong `docs/dossier/out/dfl/BAN-GIAO.md`): đăng ký đội; điền bảng đội và 2 link
trong `de-xuat-giai-phap.docx` rồi xuất PDF; quyết định về video (chờ bản sửa màn cán bộ để quay lại, hay nộp khi
chưa có); dán tên và mô tả từ `mo-ta-ngan.filled.md`; tải PDF; mỗi thành viên gõ chữ ký; xem trước, gửi, chụp xác nhận.

### Cập nhật chiều — sửa lỗi v2, nhóm tài liệu (docs-writer)

- Nguồn hồ sơ `de-xuat-giai-phap.md` khớp lại với mã: chênh ablation chỉ do lớp kiểm chứng ở cột hallucination và
  numeric_fidelity, cột answer_accuracy của `llm_unverified` có chú thích (*) (lỗi chấm `qa.py:151`); kiểm phí nhầm kênh
  đã có (`fee_channel_mismatch`), còn thiếu kiểm đơn vị; test che dữ liệu cá nhân đúng tên (`test_ask.py`); `doc_ids`
  lạ thì kiểm với toàn bộ ngữ cảnh; câu soạn tay tách dev/test theo số thứ tự; bỏ công thức "3.600 / p50".
- `mo-ta-ngan.md`: kê khai Q8_0; câu không dấu ghi số thật (placeholder `per_kind.no_diacritics`), mô tả ngắn 1.793/2.000 ký tự.
- Đính chính GPU/Q8_0 ở cuối ADR-007 và `DFL-2026-yeu-cau.md`; C8 của `ADR-007-hop-dong.md` sửa thành
  sha256(gold_procedure_id). ADR-007, ADR-008 vẫn **đề xuất**. Chưa dựng lại PDF (bước sau).

### Cập nhật 15:15 — lượt đo v2 và hồ sơ v2 (P14, P13, P7c)

Số chép từ `eval/reports/latest.json` (v2, 2026-09-25T07:34:35Z), `ablation-tthc.json`, `latency-cpu-only.json`;
số v1 từ bảng so sánh trong `eval/reports/2026-09-25.md`. Cùng tập test 138 câu, cùng chỉ mục 955 đoạn, cùng máy.

| KPI | v1 (03:07Z) | v2 (07:34Z) | Nguồn |
| --- | --- | --- | --- |
| recall@5 / answer_accuracy / chỉ phần chữ (%) | 95,65 / 84,35 / 68,7 | 95,65 / 86,09 / 69,57 | `suites.qa.metrics` |
| citation_support / hallucination (%) | 98,08 / 1,92 | 100 (ĐẠT) / 0 (ĐẠT) | `suites.qa.metrics`, `rows[].verdict` |
| numeric_fidelity / refusal_accuracy / false_escalation_rate (%) | 100 / 91,3 / 11,3 | 100 / 100 / 11,3 | `suites.qa.metrics` |
| p50 / p95 có GPU (s) | 1,284 / 2,219 | 0,908 / 1,629 | `suites.qa.metrics`, `env-tthc.json` (100 % GPU) |
| p50 / p95 chỉ CPU (s) | chưa đo | 6,155 / 14,305 | `latency-cpu-only.json` (`ollama ps`: 100 % CPU) |
| Ablation hallucination `llm_unverified` → `llm_verified` (%) | 12,5 → 1,92 | 14 → 0 | `ablation-tthc.json` |
| Khẩu ngữ / chèn lệnh / đòi làm thay (đúng/tổng) | 12/18, 3/4, 2/3 | 14/18, 4/4, 3/3 | `suites.qa.details.per_kind` |
| Không dấu / phương ngữ (đúng/tổng) | 9/17, 5/8 | 9/17, 5/8 (không đổi) | `suites.qa.details.per_kind` |
| Red-team | 50/50, 0 rò rỉ, 0 hành động thật | 92/92, 0 rò rỉ, 0 hành động thật | `suites.redteam` |
| Kết nối mạng khi đo | `localhost:11434` | `localhost:11434` | `suites.qa.details.network_hosts` |

- **Cổng QA.** Trước lượt đo v2: `uv run pytest services/agent eval data` xanh (1.100 test). Toàn bộ Python sau khi
  sửa v2: 2.216 qua, 1 đỏ (`test_check_deps.py::test_real_repo_lockfile_is_fully_allowed`, điểm dừng của người
  dùng), độ phủ 99,15 %. Nguồn: báo cáo P14 và log unit v2 của orchestrator. `make check` chưa chạy lại từ 18/9
  (`docs/status/last_check.json`).
- **Hồ sơ v2** (`docs/dossier/out/dfl/v2/`, bản v1 và v1.1 giữ nguyên): PDF 9 trang, 591.646 byte, đủ 4 hình, không còn
  placeholder (`v2/build-report.json`). Mô tả ngắn 1.909/2.000 ký tự. Mục "Chưa đạt" cập nhật theo lỗi đã sửa thật:
  mốc hiệu lực phí, giấy tờ có điều kiện ở màn cán bộ, kiểm số có đơn vị, bỏ chú thích (*) vì bộ chấm đã sửa. Thêm độ
  trễ chỉ-CPU và ghi rõ hai cấu hình.
- **Video v2:** 143,3 s, 1920×1080, 4.614.380 byte (ffprobe). Quay lại trên hệ thống thật, 9 bước có assert trên API
  thật, không tua nhanh.
- **Việc người dùng còn lại** (thứ tự trong `docs/dossier/out/dfl/v2/BAN-GIAO-v2.md`): đăng ký đội → điền bảng đội
  trong `.docx` v2 rồi xuất PDF (hoặc tạo `team-dfl.yaml` rồi dựng lại) → tải video lên YouTube (Không công khai) hoặc
  Drive → dán tên và mô tả → tải PDF → ký cam kết → xem trước → gửi → chụp xác nhận.

### Cập nhật tối — tài liệu phát hành repo công khai (docs-writer)

Mục tiêu: repo GitHub công khai làm "link sản phẩm dùng thử" của form Data for Life (chưa commit/push — orchestrator làm sau khi người dùng xác nhận).

| KPI | Giá trị | Nguồn |
| --- | --- | --- |
| Test Python (không mô hình) | 2.491: 2.484 đạt, 1 đỏ (`test_check_deps.py`, allow-list chờ chủ repo), 6 bỏ qua (không có Docker daemon, `deploy/tests`); độ phủ lõi 99,2 % | `eval/reports/engineering-2026-09-25.json` (15:28Z) |
| Test web | vitest 118/118; e2e 39 = 13 ca × 3 cỡ màn hình (lượt chạy của orchestrator, không đo lại) | `engineering-2026-09-25.json`; `apps/web/e2e/` |
| Số đo sản phẩm | không đổi so với lượt v2 | `eval/reports/latest.json`, `latency-cpu-only.json` |

- Viết lại `README.md` (6 mục bắt buộc của `check_docs.py` giữ nguyên dưới tên mới), thêm `NOTICE`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `CITATION.cff`, `docs/DEMO.md`; cập nhật `SECURITY.md`, `CHANGELOG.md`.
- Số "2.216 test" của lượt 15:15 đã cũ (thêm test sau đó, gồm `scripts/tests/test_quickstart.py`); README dùng số đo lại.
- Còn chờ: ảnh `docs/media/*` và `scripts/quickstart.py` (agent media làm song song); thay `OWNER/REPO` trong README,
  `docs/DEMO.md`, `CITATION.cff`; thay `<!-- VIDEO_URL -->` sau khi tải video lên YouTube.

## 2026-09-19 (Thứ Bảy) — Pha A / ưu tiên theo yêu cầu người dùng: hoàn thiện hồ sơ giấy trước, mã tiếp tục sau khi hạn mức tuần reset (24/9)

| KPI | Giá trị | Nguồn |
| --- | --- | --- |
| Epic đang làm và % test xanh | **E01** (tích hợp K còn dở) + **DOSSIER bản giấy**; 1.426/1.427 test Python đạt, web 33/33, coverage lõi 99,4 % | `eval/reports/engineering.json` (19/9) |
| Số test / e2e | 1.427 Python (1 chưa đạt: allow-list thư viện chưa cập nhật; xem dưới), 33 vitest; e2e chưa chạy | `scripts/collect_engineering_metrics.py` |
| Eval quick gần nhất | chỉ bộ red-team chạy (5 bộ còn lại `skipped` — chưa có tập đánh giá/GPU) | `eval/reports/latest.json` |
| Số lỗi red-team | **0/50** (guardrail, không mô hình); ablation tắt guardrail: **45/50** đòn thành công (rò rỉ 26, thao tác trái phép 31) | `eval/reports/redteam-2026-09-19.md`, `redteam-ablation.json` |
| Độ trễ p95 staging | chưa có staging | — |
| Chi phí GPU/API lũy kế | 0 giờ GPU; 0 đ API | — |
| Câu hỏi đang chờ người dùng | như 18/9 (ADR-002, ADR-006, TTS, ngưỡng escalate, đối tác pilot, GPU) + điền `docs/dossier/private/team.yaml`, link Drive, link repo | `docs/dossier/HUONG-DAN-NOP.md` |
| Rủi ro mới | Hạn mức tuần của Claude Code đã chạm (reset 24/9 5:00) — các gói E01 còn dở: H (eval: `loadtest/k6.js`, `pilot/README`, tests), I (chưa verify), K (tích hợp: `config/allowed-deps.yaml` thiếu ~650 gói mới → test `check_deps` đỏ → `make check` chưa xanh), plugin `ctcv-kit` chưa sinh | phiên 18–19/9 |

Hồ sơ giấy 19/9: `docs/dossier/out/01_TaiLieuDuAn_CTCV.pdf` **16 trang** (Word đếm), 13 mục MẪU 3, 3 hình (2 sơ đồ + 1 ảnh thật PWA), số liệu đọc tự động từ `eval/reports/`; chế độ chính thức đã chạy thử qua mọi cổng với file đội giả định ngoài repo (0 dấu treo, 5 văn bản luật đã xác minh). `06_KeKhaiAI.pdf`, `07_PromptLog.zip` đã sinh. Việc người dùng: `docs/dossier/HUONG-DAN-NOP.md`.

## 2026-09-18 (Thứ Sáu) — Pha A / mốc ADR-006: E01 bootstrap (18–19/9)

| KPI | Giá trị | Nguồn |
| --- | --- | --- |
| Epic đang làm và % test xanh | **E01** — 11 gói song song; lúc 11:15: F, A (trừ `plugins/`), B (bản 2, đã đồng bộ tên module với skeleton), C, D, E, G, I, J đã có mã + test; H: data/training xong, eval đang ghi (thiếu `ctcv_eval.redteam`/`loadtest`/`pilot`, `scenarios.jsonl`, `k6.js`); K chưa chạy — `make check QUICK=1` chưa có kết quả; `check_docs.py` xanh, hooks 139/139 xanh | cây repo lúc 11:15; `uv run pytest --collect-only` |
| Số test / e2e | ≈ 1.360 ca gom được, chưa chạy trọn (`libs/core` 105, `services/api` 216, `services/agent` 240, `speech` 27, `vision` 43, `sandbox` 136, `drills` 120, `data` 46, `training` 46, `scripts` 61, `tests/` 110, `deploy` 62, `docs/dossier/build` 15, `.claude/hooks` 139; `eval` 0); e2e smoke `apps/web/e2e` chỉ chạy khi `E2E=1` | `uv run pytest --collect-only` 11:15 |
| Eval quick gần nhất | chưa có (chưa có máy GPU; `make gate` chỉ chạy từ E05) | — |
| Số lỗi red-team | chưa chạy — `eval/redteam/scenarios.jsonl` và runner `ctcv_eval.redteam` chưa có (gói H đang ghi); `make redteam` in CHƯA HIỆN THỰC | — |
| Độ trễ p95 staging | chưa có staging (E12-lite dự kiến 21–22/9) | — |
| Chi phí GPU/API lũy kế | 0 giờ GPU / 300; 0 đ API | — |
| Câu hỏi đang chờ người dùng | (1) ADR-002/D9: một model Qwen3.5-9B cho cả planner + đọc ảnh hay giữ Qwen3-VL-8B (cần spike 2 giờ trên GPU); (2) ADR-006: duyệt lịch 3 pha, tuyến trường 30/9, 7 mục cắt phạm vi (APK → PWA offline; kèm cặp app thật → hướng phát triển; E06/E07 → Pha D; 6 kịch bản; ablation thành phần…); (3) tên sản phẩm + domain; (4) TTS (Piper vs F5/viXTTS); (5) ngưỡng escalate 0,6/0,7; (6) đối tác pilot tầng 2; (7) nhà cung cấp GPU | epics/E01, E04, E05, PILOT; ADR-002, ADR-006 |
| Rủi ro mới | **Hạn nộp (CF-01/S1, blocker):** lịch D1–D21 của plan đặt hồ sơ ở 7–8/10, sau hạn tuyến trường 30/9; hạn nội bộ trường chưa biết (N02) — phải gọi Đoàn trường/CTSV + BTC **hôm nay**. **GPU chưa thuê** (S7): mọi eval có model bị chặn; Pha A có thể phải chạy profile `cpu` (Qwen3.5-2B). **Repo chưa có commit** (CC-11): worktree/subagent song song chưa an toàn; prompt log của phiên này chỉ được ghi nếu hook đã cài trước (S10). **Đội hình chưa cam kết** (N08). **Giấy xác nhận SV, domain `.vn`, GitHub Pro** có lead time (N16). **3 văn bản pháp luật chưa xác minh** (LEG-11). **Gãy `uv run` toàn repo** khi một gói thiếu `README.md` (hatchling `readme`) — đã xảy ra với agent/training, K kiểm mọi gói. **File lạ** `hd_test.txt`, `hd_test2.txt` ở gốc (xóa trước commit đầu). **Hồ sơ mục 2** 629 từ > ngân sách 605 (test `test_word_budget_respected` đỏ — gói J). **ADR-006 ≈ 3 trang** (spec ≤ 1 trang) — cắt lịch theo ngày sang phụ lục sau khi người dùng chốt | docs/analysis/2026-09-18-review-findings.md; verifier WP B 18/9 |

Sớm/trễ so với ADR-006: đúng ngày (E01 18–19/9). Việc hôm nay (Claude): hoàn tất 11 gói, tích hợp K, `make check QUICK=1` xanh, PR "[E01] Khung repo". Việc người dùng hôm nay (brief §17.13, ADR-006 mục 6): gọi Đoàn trường/CTSV + BTC (4 câu N02); chốt 3 thành viên + lịch thi; nộp đơn giấy xác nhận SV; thuê GPU (SSH + `nvidia-smi` trước 20/9); GitHub Pro/Student Pack; tạo commit đầu `chore(E00)`; xuất hội thoại soạn 3 tài liệu vào `docs/prompt-log/pre-D1/`; trả lời 7 câu hỏi đang chờ.
