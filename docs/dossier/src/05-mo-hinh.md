# 5. Thuật toán, mô hình, phương pháp hoặc công cụ trí tuệ nhân tạo được sử dụng

> Nội dung trình bày: Liệt kê thuật toán, mô hình, phương pháp hoặc công cụ trí tuệ nhân tạo đã sử dụng; nêu vai trò của từng thành phần trong quá trình xây dựng, vận hành sản phẩm.

## 5.1. Mô hình

Mọi mô hình đều mở và tự host trên máy chủ do đội vận hành; không API thương mại nào trên đường xử lý của người dùng; giấy phép đối chiếu thẻ mô hình ngày 18/9/2026.

| Thành phần | Mô hình | Giấy phép | Cách chạy | Vai trò | Phần đội tự làm |
| --- | --- | --- | --- | --- | --- |
| Huấn luyện viên (planner) | Qwen3.5-9B | Apache-2.0 | vLLM, AWQ 4-bit, 1 GPU 24 GB | Xác nhận ý định, chọn tool, sinh câu ≤ 2 câu | Prompt có cấu trúc (bản nộp); LoRA SFT + DPO (Pha D) |
| Đọc màn hình (VLM) | Qwen3.5-9B, **cùng instance** (đa phương thức native); phương án B: Qwen3-VL-8B | Apache-2.0 | vLLM multi-LoRA: kèm cặp dùng mô hình gốc, huấn luyện viên dùng adapter | JSON kín: `screen_id` thuộc danh mục, `element_id`, khung highlight | Prompt, schema; chốt sau spike trên GPU (ADR-002) |
| LLM cách ly, LLM-judge | Cùng mô hình gốc, prompt riêng, không tool | Apache-2.0 | vLLM | Văn bản không tin cậy → schema kín; chấm hội thoại và trích dẫn offline | Schema, prompt, hiệu chỉnh judge bằng 50 mẫu người |
| Đường CPU dự phòng | Qwen3.5-2B (GGUF Q4_K_M) | Apache-2.0 | llama.cpp | Dev không GPU, hackathon, fallback khi GPU tắt | Đo chênh lệch với 9B |
| Nhận dạng giọng nói | PhoWhisper-small (VinAI) | BSD-3-Clause | faster-whisper INT8, xử lý trong bộ nhớ | ASR chịu giọng vùng miền | Tập đánh giá tự ghi theo giọng/tuổi |
| Tổng hợp giọng nói | Piper (vi_VN) | MIT | CPU, stream theo câu, cache ~500 câu | Đọc câu huấn luyện viên, thoại mô phỏng có nhãn | Tiêu chí: giấy phép mở cả checkpoint, RTF CPU < 0,3, MOS ≥ 3,5 |
| Truy xuất | BAAI/bge-m3 + bge-reranker-v2-m3 | MIT | Qdrant hybrid (dense + BM25) | Tìm, xếp hạng đoạn để trích dẫn | Chunk theo bước, metadata, ngưỡng kiểm chứng |
| Phát hiện phần tử giao diện | YOLOX-Tiny (ONNX) | Apache-2.0 | — | Khung nút/ô nhập | **Hoãn khỏi v1.0**: grounding của VLM đủ cho ảnh sandbox; cấm Ultralytics (AGPL-3.0) |

## 5.2. Phương pháp

1. **Sandbox máy trạng thái.** Kịch bản là JSON gồm màn hình, phần tử, hành động hợp lệ, lỗi thường gặp; engine `apply(state, event)` quyết định bước kế tiếp không cần LLM nên bước sandbox nhanh, đúng, đo được (bước, lần sai, gợi ý).
2. **Agent huấn luyện viên có công cụ (agentic RAG).** Planner chỉ nhìn trạng thái có cấu trúc và kết quả của 8 tool trong danh sách đóng (đọc trạng thái, bước kế, tìm hướng dẫn, kiểm chứng trích dẫn, drill, ghi tiến độ, gọi tình nguyện viên; side effect chỉ `none | sandbox | log`). Câu có dữ kiện phải qua `verify_citation`; dưới ngưỡng tin cậy thì nói "tôi không chắc" và mời tình nguyện viên.
3. **Tách luồng điều khiển khỏi dữ liệu không tin cậy (CaMeL).** Văn bản dán, tin nhắn mẫu, nội dung web đi qua LLM cách ly không tool, chỉ trả schema kín (enum ý định, mã dấu hiệu, số tiền, danh mục cơ quan); planner không bao giờ nhận chuỗi tự do từ nguồn không tin cậy.
4. **Sư phạm mã hóa thành hành vi:** xác nhận ý định trước khi chỉ; một bước một lần, tối đa 2 câu, kết thúc bằng hành động có màu và chữ trên nút; can thiệp trước lần bấm sai thứ hai; ôn cách quãng ngày 2, 5, 12; không thao tác thay người dùng.

## 5.3. Công cụ AI dùng trong quá trình xây dựng (kê khai)

- **Claude Code (Anthropic, Claude Fable 5.1):** viết mã, test, tài liệu theo 14 epic do đội điều khiển; mọi phiên tự ghi thành Prompt Log (mục 13).
- **Sinh dữ liệu tổng hợp và LLM-judge:** mô hình mở tự host (Qwen3.5-9B) hoặc mô hình mở cỡ lớn qua nhà cung cấp cho phép dùng đầu ra (kê khai tên, giấy phép, ngày kiểm tra); không dùng API cấm huấn luyện từ đầu ra.
- **Thư viện nền:** FastAPI, SQLAlchemy, React + Vite, vLLM, faster-whisper, Qdrant, Playwright, k6, Docker Compose (MIT/Apache/BSD; allow-list `config/allowed-deps.yaml` kiểm trong `make audit`).
