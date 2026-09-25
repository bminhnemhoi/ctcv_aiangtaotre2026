# hackathon — Bộ kit và kế hoạch cho vòng khu vực (hackathon 2 ngày, 60 % điểm) và thử thách 12 giờ ở chung kết

Nguồn: `docs/idea.md` §13, `docs/prompt.md` §6 (`/hackathon`), `docs/competition/BTC-2026-yeu-cau.md` §3, ADR-006 Pha B; phát hiện CF-05, S4, CF-09, CC-13. Đề và dataset BTC phát sẽ được đặt vào `hackathon/input/` (gitignore nếu BTC cấm phân phối; `.gitkeep` giữ thư mục).

## 1. Lịch thật
- **Pha B 1–9/10/2026**: tách kit + 2 diễn tập (ADR-006). Vòng khu vực miền Nam **10–11/10 (T7–CN) tại TP.HCM**: "hackathon trực tiếp 2 ngày trên dataset và bài toán xã hội nóng BTC cung cấp". Chung kết **20–22/11 Hà Nội**: "thử thách cải tiến 12 giờ" (BTC chưa công bố nội dung — CF-09), demo, phản biện, 48 giờ ổn định.
- Câu hỏi phải hỏi BTC trước 1/10 (N02 câu 4): được dùng công cụ AI / internet / máy chủ riêng không; có nộp prompt log của hackathon không; giờ làm việc mỗi ngày (giả định 2 × 10 giờ; có biến thể 48 giờ liên tục bên dưới).

## 2. Bộ kit (`plugins/ctcv-kit`, sinh bằng `make plugin` qua `scripts/sync_plugin.py`; kiểm tay bằng `claude plugin validate plugins/ctcv-kit`)
| Thành phần | Nguồn trong repo CTCV | Dùng lại cho bài toán mới |
| --- | --- | --- |
| Agents + skills + hooks Claude Code | `.claude/` (bỏ `hooks`/`mcpServers`/`permissionMode` khỏi agent frontmatter; `hooks.json` từ settings) | Cài trong 15 phút: `claude --plugin-dir plugins/ctcv-kit` trong repo mới |
| Ingestion | `data/src/ctcv_data/pipeline/` (crawl robots-aware, PDF/CSV/Excel/HTML → chunk có metadata) | bất kỳ dataset văn bản/bảng BTC phát |
| RAG có trích dẫn + kiểm chứng | `services/agent` (`search_guides`, `verify_citation`, `requires_citation`) | hỏi đáp có căn cứ về chủ đề mới |
| Agent planner + tool router + guardrail | `services/agent` (thêm tool = 1 file Python có schema, vào `config/tools.yaml`) | mô phỏng quy trình bất kỳ |
| Sandbox engine | `sandbox/` (máy trạng thái JSON, validator) | khai báo, đăng ký, xử lý sự cố… |
| Giọng nói | `services/speech` (ASR/TTS) | giao diện cho người dân |
| Eval harness + red-team + load | `eval/` (`make eval`, `make redteam`, `k6.js`) | bảng kết quả trong giờ đầu |
| Deploy CPU-only + status page | `deploy/` profile `cpu` (`planner_small` Qwen3.5-2B GGUF, PhoWhisper-tiny) — không phụ thuộc GPU thuê | demo chạy trên laptop trong 30 phút |
| **ds-kit** (bổ sung Pha B — CF-05/S4) | mới trong `plugins/ctcv-kit/skills/ds-kit/`: EDA tự động (pandas/polars → HTML), baseline bảng (scikit-learn/LightGBM + cross-validation + SHAP), pipeline văn bản tiếng Việt (underthesea/PhoBERT/bge-m3), geospatial (geopandas/folium), time-series cơ bản, dashboard nhanh (Streamlit/Gradio), sinh slide + báo cáo theo mẫu BTC | dataset dạng bảng/địa lý/chuỗi thời gian mà kit RAG/agent không phủ; thư viện thêm vào allow-list riêng của kit (ADR khi tách) |
| Template hồ sơ, slide, script demo | `docs/dossier/video/`, `docs/dossier/build/` | tài liệu nộp trong 2 giờ cuối |

Chế độ CPU-only là mặc định của kit (laptop 3 người, không chắc có internet/GPU tại địa điểm); nếu BTC cho dùng máy chủ riêng → trỏ `VLLM_BASE_URL` về máy GPU thuê.

## 3. Kế hoạch 2 ngày (giả định 2 × 10 giờ, 8:00–18:00; phân vai 3 người)
| Giờ | Việc | Người A (điều phối + Claude Code) | Người B (dữ liệu/model) | Người C (UI/demo/slide) | Mốc |
| --- | --- | --- | --- | --- | --- |
| 0–2 | Đọc đề, khám phá dataset (`architect` chỉ đọc), đề xuất 2 bài toán con chứng minh được bằng số; **chọn** | chạy `/hackathon`, ghi quyết định | EDA nhanh (ds-kit) | dựng khung slide 1 trang "bài toán – số đo" | H2: bài toán chốt |
| 2–6 | Ingestion + RAG/baseline + eval baseline | ingestion | baseline + eval harness | mock UI | H6: **bảng số baseline** |
| 6–10 | Tính năng lõi trên kit (backend ∥ data ∥ frontend) | agent/tool mới | dữ liệu thật, cải tiến model | UI chữ to/dashboard | **H10: phải có demo chạy end-to-end** (CPU) |
| 10 (nghỉ đêm) | commit, `/daily`, ghi rủi ro | | | | |
| 10–14 | QA + red-team + deploy CPU/status page | qa/reviewer | eval lần 2 | deploy + status | H14: URL demo |
| 14–17 | Kết quả + ablation + "kết quả chưa đạt" | tổng hợp | ablation | slide kết quả | H17: bảng kết quả cuối |
| 17–19 | Slide, script demo, tập thuyết trình 2 lần | phản biện dự kiến | số liệu | dựng slide/demo | H19: tập xong |
| 19–20 | Dự phòng, nộp | | | | nộp |
`/daily` mỗi 4 giờ (DAILY.md); prompt log ghi tự động nếu BTC yêu cầu. Biến thể 48 giờ liên tục (idea §13): 0–2 / 2–6 / 6–14 / 14–20 / 20–26 / 26–34 / 34–40 / 40–48 — cùng thứ tự, thêm ca ngủ luân phiên.

## 4. Diễn tập (Pha B)
- **#1 — CN 4/10, 8 giờ, đề dạng bảng** (ví dụ: dataset cảnh báo thiên tai cấp xã / thủ tục hành chính dạng CSV): chạy từ đề đến demo bằng kit + ds-kit; đo giờ đạt mốc H6/H10; ghi chỗ tắc vào `docs/status/DAILY.md`; sửa kit 5–7/10.
- **#2 — T5 8/10, 6 giờ, đề dạng văn bản** (RAG + agent): kiểm đường CPU-only, thêm 1 tool ngoài (< 1 giờ nhờ schema), tập thuyết trình 5 phút.
- Cả 3 thành viên cài Claude Code + kit trên laptop riêng, mỗi người sở hữu một nhánh kit và có thể giải thích mô-đun mình phụ trách (N10).

## 5. Thử thách cải tiến 12 giờ (chung kết) — kế hoạch giờ
Nội dung chưa được BTC công bố (CF-09); chuẩn bị 3 hướng ưu tiên (idea §13) + 1 hướng dự phòng:
| Giờ | Việc |
| --- | --- |
| 0–1 | Đọc đề; chọn 1–2 cải tiến đo được; đo **trước** (p95, red-team, eval) — có sẵn bộ đo |
| 1–5 | Ưu tiên 1: **tối ưu hệ thống** (batching vLLM, cache TTS, lượng tử hóa thấp hơn, kịch bản "giảm 30 % độ trễ") |
| 5–8 | Ưu tiên 2: **bảo mật** (mở rộng red-team 200 → 250, checklist OWASP Agentic trước/sau, test hồi quy) |
| 8–10 | Ưu tiên 3: **tích hợp tool/nguồn mới** cho agent (< 1 giờ mỗi tool nhờ schema; đã tập ở diễn tập #2) |
| 10–11 | Dự phòng: nếu đề là "thêm nhóm người dùng / tính năng theo yêu cầu giám khảo" → kịch bản sandbox mới bằng JSON + UI |
| 11–12 | Đo **sau**, bảng trước/sau, slide 3 trang, tập phản biện |
Ràng buộc: giữ 3 nguyên tắc bất biến; không deploy ngoài quy trình đóng băng lên bản đang chấm (làm trên nhánh/máy riêng); trực ca vẫn giữ.

## 6. Phản biện dự kiến (idea §13) — câu trả lời chuẩn bị trong `docs/dossier/src/` ("Giải thích cho người", 10 câu)
Khác gì ChatGPT · người cao tuổi dùng được không (số pilot, SUS, giọng địa phương) · có thay TNV không · dữ liệu ở đâu, giấy phép · an toàn lừa đảo ngược · vì sao sandbox không phải app thật · fine-tune thắng base bao nhiêu (trung thực) · chi phí tự host · prompt log và phần đội tự xây · lộ trình sau cuộc thi.
