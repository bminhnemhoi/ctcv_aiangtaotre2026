# Dàn ý 12 slide cho video thuyết trình 5 phút

Nguyên tắc: mỗi slide ≤ 25 từ + 1 hình/bảng thật; chữ ≥ 28 pt; số liệu chỉ lấy từ `eval/reports/latest.json`;
tính năng chưa có trong bản tag chỉ xuất hiện ở slide 11 "Lộ trình". Dựng bằng pptx hoặc HTML → PDF, tỷ lệ 16:9.

| # | Tiêu đề | Nội dung | Hình / bảng |
| --- | --- | --- | --- |
| 1 | Cầm Tay Chỉ Việc (CTCV) | Trợ lý AI đồng hành Bình dân học vụ số · Bảng C · Trường Đại học Tôn Đức Thắng · 3 thành viên | Logo trường, ảnh đội |
| 2 | Bài toán | 13.124 đội hình, 2,5 triệu người được hỗ trợ; 3 điểm yếu: không lặp lại, rủi ro tài khoản thật, không đo được | Bảng 1 (mục 1), ảnh lớp học có phép |
| 3 | Người dùng | Cô Lan 63 tuổi · chú Bảy 58 tuổi giọng miền Tây · bà Hương 70 tuổi; tình nguyện viên; cán bộ Đoàn | 3 persona + hành trình 2 buổi |
| 4 | Sản phẩm: 5 mô-đun | Sandbox học bằng làm · hỏi có căn cứ · vắc-xin lừa đảo · kèm cặp trên ảnh sandbox · dashboard | Ảnh màn hình thật của bản tag |
| 5 | Demo 1: sandbox | "Tôi muốn chuyển tiền cho con" → xác nhận ý định → 4 bước, câu ≤ 2 câu | Clip 30 s từ video demo |
| 6 | Demo 2: trích dẫn và vắc-xin | Câu trả lời có nút "Nguồn"; tình huống "công an gọi" có nhãn [Mô phỏng] | Clip 30 s |
| 7 | Kiến trúc | Agent + 8 tool whitelist; LLM cách ly schema kín (CaMeL); sandbox máy trạng thái không gọi LLM | figures/10-kien-truc.png |
| 8 | Mô hình và làm chủ | Qwen3.5-9B tự host (Apache-2.0), PhoWhisper (BSD-3), Piper (MIT), bge-m3 (MIT); bản nộp: prompt có cấu trúc; Pha D: LoRA SFT + DPO | Bảng mô hình rút gọn (mục 5) |
| 9 | Kết quả đo được | Recall@5 {{eval:rag.recall_at_5}} · citation-support {{eval:qa.citation_support}} % · red-team {{eval:redteam.leaks}}/{{eval:redteam.size}} · p95 sandbox {{eval:latency.sandbox_p95_s}} s · SUS {{eval:pilot.sus}} (n = {{eval:pilot.n}}) | Bảng 8.1 rút gọn, biểu đồ trước/sau |
| 10 | Kết quả chưa đạt | Chưa fine-tune · WER giọng địa phương {{eval:audio.wer_regional}} % · {{eval:sandbox.scenario_count}}/12 kịch bản · chưa có nhóm đối chứng · APK và kèm cặp app thật hoãn | Danh sách 8.4 |
| 11 | Triển khai và lộ trình | `docker compose up`, Apache-2.0, < 20.000 đ/1.000 lượt; URL + status sống đến chung kết; Pha B kit hackathon → Pha D pilot 30 người, fine-tune, 12 kịch bản | Trang status thật, bảng 4 pha |
| 12 | Cảm ơn | Link repo · link Drive (Prompt Log, minh chứng) · "Không thay tình nguyện viên — nhân bản năng lực của họ" | QR repo + Drive |
