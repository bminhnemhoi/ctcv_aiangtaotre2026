# Kịch bản video thuyết trình (≤ 5 phút) — Cầm Tay Chỉ Việc (CTCV)

Thành phần hồ sơ số 2. Khung thời gian theo `docs/idea.md` §12, nội dung điều chỉnh cho **bản nộp sơ bộ** (CF-08):
chỉ nói về những gì bản được gắn tag nộp có thật; kết quả nêu bằng số từ `eval/reports/latest.json` hoặc nói rõ
"chưa đo". Slide theo `slide-outline.md`. Người nói: 3 thành viên thay phiên (mỗi người ≥ 1 phân đoạn) để Hội đồng
thấy cả đội hiểu hệ thống (N10). Tên đội, tên sản phẩm, Bảng C và trường hiện trên hình trong 5 giây đầu.

| Thời gian | Slide | Người nói | Lời thoại (đọc tự nhiên, ≈ 130 từ/phút) | Hình trên màn |
| --- | --- | --- | --- | --- |
| 0:00–0:10 | 1 | TV1 | "Chúng tôi là đội Cầm Tay Chỉ Việc, Trường Đại học Tôn Đức Thắng, Bảng C. Sản phẩm: trợ lý AI đồng hành phong trào Bình dân học vụ số." | Tên đội, tên sản phẩm, logo trường, 3 gương mặt |
| 0:10–0:40 | 2 | TV1 | "Hơn 13.000 đội hình thanh niên đã hỗ trợ gần 2,5 triệu người dân. Nhưng cô Lan 63 tuổi bán tạp hóa vẫn phải hỏi lại mỗi lần kê khai doanh thu; dạy trên tài khoản thật thì sợ bấm nhầm mất tiền; và không ai đo được cô đã tự làm được chưa. Ba điểm yếu: không lặp lại được, rủi ro, không đo được." | Ảnh lớp Bình dân học vụ số (có phép) + 3 số liệu Bảng 1 |
| 0:40–1:20 | 3–4 | TV2 | "CTCV là sandbox học bằng làm: người dân nói 'tôi muốn chuyển tiền cho con', huấn luyện viên AI xác nhận ý định rồi chỉ từng bước bằng giọng nói trên ứng dụng mô phỏng — không đụng tài khoản thật. Năm mô-đun: sandbox, hỏi có căn cứ với trích dẫn, vắc-xin lừa đảo, kèm cặp trên ảnh sandbox, dashboard cho tình nguyện viên. Chữ to 20 pt, một hành động mỗi màn hình, luôn có nút gọi tình nguyện viên." | Màn hình thật của bản tag: sandbox + nút micro |
| 1:20–2:40 | 5–6 | TV2 | Demo nhanh (cắt từ `03_VideoDemo.mp4`, không lặp nguyên): 1 kịch bản sandbox 4 bước với câu ≤ 2 câu; 1 câu hỏi có trích dẫn kèm nút "Nguồn"; 1 tình huống vắc-xin lừa đảo với nhãn "[Mô phỏng]" và "3 việc phải làm". Lời dẫn ngắn, để tiếng huấn luyện viên vang lên. | Ghi màn hình thật |
| 2:40–3:30 | 7–8 | TV1 | "Kiến trúc: agent huấn luyện viên có 8 công cụ trong danh sách đóng, chạy trên Qwen3.5-9B tự host qua vLLM; văn bản không tin cậy đi qua LLM cách ly trả về schema kín — planner không bao giờ nhận chuỗi tự do. Bước sandbox không gọi LLM nên p95 dưới 1 giây. Không lưu CCCD, OTP, mật khẩu; ảnh xóa sau 60 giây. Bản nộp dùng mô hình gốc với prompt có cấu trúc; fine-tune LoRA là kế hoạch Pha D." | Sơ đồ kiến trúc (figures/10-kien-truc.png), bảng mô hình + giấy phép |
| 3:30–4:20 | 9–10 | TV3 | "Kết quả đo được tại ngày nộp: recall@5 {{eval:rag.recall_at_5}}, citation-support {{eval:qa.citation_support}} %, red-team {{eval:redteam.leaks}} rò rỉ trên {{eval:redteam.size}} kịch bản, thử nghiệm sơ bộ {{eval:pilot.n}} người 50+ với SUS {{eval:pilot.sus}}. Chúng tôi nói thẳng chỗ chưa đạt: WER giọng địa phương {{eval:audio.wer_regional}} %, chưa fine-tune, mới {{eval:sandbox.scenario_count}} trên 12 kịch bản, chưa có nhóm đối chứng — pilot 30 người diễn ra 27/10–9/11." | Bảng 8.1 + biểu đồ trước/sau (nếu có) |
| 4:20–5:00 | 11–12 | TV3 | "Triển khai: một lệnh docker compose, mã Apache-2.0, chi phí dưới 20.000 đồng mỗi 1.000 lượt khi Tỉnh đoàn tự host; URL công khai và trang status sống đến chung kết. Lộ trình: đủ 12 kịch bản, fine-tune, pilot 30 người, rồi gói 'lớp Bình dân học vụ số 2.0' cho từng phường. Cảm ơn Hội đồng." | Trang status thật, lộ trình 4 pha, link repo + Drive |

## Quy tắc quay và dựng

- Quay 2 lần liên tục, chọn bản tốt; micro cài áo; phông nền lớp học hoặc phòng lab; không đọc slide.
- Tổng thời lượng ≤ 300 s (kiểm bằng `ffprobe`); phụ đề tiếng Việt cho mọi đoạn có tiếng huấn luyện viên.
- Mọi số trong lời thoại phải khớp `eval/reports/latest.json` tại ngày quay; nếu chưa có số, nói "chưa đo" — không ước.
- Không đưa tính năng chưa có trong bản tag (APK offline, kèm cặp app thật, YOLOX, fine-tune) vào phần "đã làm".
- Xuất `02_VideoThuyetTrinh.mp4` 1080p, H.264, ≤ 500 MB; tên đội + tên sản phẩm ở khung hình đầu.
