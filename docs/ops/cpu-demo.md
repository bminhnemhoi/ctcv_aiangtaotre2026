# Chạy demo CTCV cục bộ (máy dev Windows; Ollama tự nạp mô hình lên GPU nếu máy có; chưa đo độ trễ khi chỉ có CPU)

Tài liệu cho gói P9 của ADR-007 (Data for Life 2026, đề DA940-01). Demo chạy thật: API hỏi đáp thủ tục
(`/v1/coach/ask`), đối chiếu hồ sơ cho cán bộ (`/v1/coach/intake-check`) và web, dùng chỉ mục 107 thủ tục
của Cổng Dịch vụ công Bộ Công an và Ollama cục bộ. Không có dữ liệu giả hay mock.

## Điều kiện

| Thành phần | Kiểm tra |
| --- | --- |
| Ollama chạy ở `serving.endpoint` của `config/rag.yaml` (mặc định máy cục bộ) | `ollama list` có `bge-m3` và `qwen3.5:2b` |
| Chỉ mục TTHC | có `data/clean/tthc/index/index_meta.json`; nếu chưa: `uv run python -m ctcv_data.pipeline chunk_embed --online` |
| Gói Python và Node | `uv sync --all-packages`, `pnpm install` |
| Cổng trống | `ports.api` và `ports.web` trong `config/app.yaml` (mặc định 8000 và 5173) |

RAM tối thiểu khoảng 8 GB trống cho hai model. Không nạp model Ollama khác trong lúc demo.

## Chạy

Trong Git Bash, tại gốc repo:

```bash
uv run python scripts/dev_cpu.py                      # dựng API + web, nạp model, in URL; Ctrl-C để dừng
uv run python scripts/dev_cpu.py --show-credentials   # in thêm mã lớp và mật khẩu cán bộ tạm thời
uv run python scripts/dev_cpu.py --run <lệnh ...>     # chạy lệnh với cùng biến môi trường rồi dừng stack
```

Tùy chọn khác: `--no-web` (chỉ API), `--no-warmup` (bỏ lượt hỏi nạp model), `--timeout <giây>` (chờ
`/v1/health`). Script:

1. kiểm Ollama có đủ model trong `config/rag.yaml` và chỉ mục đã dựng;
2. sinh bí mật tạm (`CTCV_DEMO_QR_TOKEN`, `CTCV_DEMO_STAFF_PASSWORD`, `JWT_SECRET`) nếu biến chưa có;
3. chạy `uv run ctcv-api` và `vite --host 127.0.0.1 --strictPort` làm tiến trình con, log ở
   `<thư mục tạm>/ctcv-dev-cpu/{api,web}.log`;
4. chờ `/v1/health`, gọi một lượt join + ask để nạp model (lượt đầu chậm hơn);
5. in URL: người dân `http://127.0.0.1:<ports.web>/#hoi-thu-tuc`, cán bộ `.../#can-bo`
   (tài khoản `demo.staff_username` trong `config/rag.yaml`). Vào lớp tự động bằng `/?lop=<mã lớp>#hoi-thu-tuc`
   (mã lớp chỉ in khi có `--show-credentials`).

Dừng bằng Ctrl-C: script tắt cả cây tiến trình con (Windows dùng `taskkill /T`).

## Kịch bản demo (C9)

Người dân: "Đăng ký thường trú mất bao nhiêu tiền?" → bấm nút xanh "Nguồn" → "Làm căn cước cho cháu 14 tuổi
cần mang giấy tờ gì?" → "Thủ tục đăng ký kết hôn cần những gì?" (ngoài kho: trả lời "không chắc" và mời tình
nguyện viên) → "Có người xưng công an gọi xin mã OTP, tôi có đọc không?" (câu an toàn cố định).
Cán bộ: đăng nhập → tìm "đăng ký tạm trú" → chọn trường hợp hồ sơ → đánh dấu giấy tờ đã nhận → xem danh sách
thiếu và câu nhắn cho người dân.

## Dự phòng khi model chậm hoặc lỗi

```bash
CTCV_RAG_COMPOSE_MODE=template_only uv run python scripts/dev_cpu.py
```

Chế độ `template_only` bỏ bước sinh câu bằng LLM, trả câu mẫu tất định dựng từ bản ghi thủ tục (vẫn có trích
dẫn tới trang nguồn). Embedding `bge-m3` vẫn cần cho truy xuất; khi embedder lỗi, truy xuất lùi về BM25
và kết quả đánh dấu `degraded`. Đổi endpoint Ollama bằng `CTCV_OLLAMA_BASE_URL`.

## An ninh

- API và web chỉ nghe `127.0.0.1`; không mở cổng ra mạng. Muốn trình chiếu trên máy khác thì dùng màn hình
  chia sẻ, không đổi `--host`.
- Bí mật demo sinh bằng `secrets.token_urlsafe(24)` cho từng lượt chạy, chỉ nằm trong biến môi trường của
  tiến trình con; không ghi ra file, không in ra nếu thiếu `--show-credentials`. Nếu đã đặt sẵn biến thì
  script giữ nguyên giá trị đó.
- Script từ chối chạy khi `CTCV_ENV=prod`; API cũng từ chối khởi động ở prod khi có biến demo (C6).
- `/v1/coach/ask` không trả `diagnostics`; log không ghi nguyên văn câu hỏi. Script không đọc `.env`
  (API tự nạp `.env` nếu có; biến do script đặt được ưu tiên hơn).

## Kiểm chứng

- `uv run pytest scripts/tests/test_dev_cpu.py -q` — dựng env, tham số, vòng chờ health, warm-up và việc
  không in bí mật (không khởi động tiến trình thật).
- Smoke trên stack thật: chạy một script kiểm tra qua `--run` (join → ask 3 câu → login cán bộ →
  intake-check); script đọc `CTCV_DEMO_QR_TOKEN` và `CTCV_DEMO_STAFF_PASSWORD` từ môi trường.

## Sự cố thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `LỖI: Không gọi được Ollama` | mở ứng dụng Ollama, thử `ollama list` |
| `Ollama thiếu model` | chạy lệnh `ollama pull` script in ra |
| `API không lên /v1/health` | xem 20 dòng cuối log script in ra; kiểm cổng 8000 có bị chiếm không |
| Web báo cổng bận | tắt tiến trình đang giữ `ports.web` (`--strictPort` không tự đổi cổng) |
| Trả lời quá chậm | dùng `CTCV_RAG_COMPOSE_MODE=template_only` |
