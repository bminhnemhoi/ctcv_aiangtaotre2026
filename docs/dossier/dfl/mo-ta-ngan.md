# Nội dung dán vào form nộp Data for Life 2026 (đề DA940-01)

Cách dùng: công cụ dựng hồ sơ thay các placeholder `{{eval:…|chưa đo}}` bằng số trong `eval/reports/latest.json`
và ghi ra `docs/dossier/out/dfl/mo-ta-ngan.filled.md`. Chưa có số thì giữ chữ "chưa đo". Anh/chị dán từ bản `.filled.md`,
không dán bản này. Giới hạn trên form (`docs/competition/DFL-2026-yeu-cau.md` §1.5): Tên giải pháp ≤ 400 ký tự;
Mô tả ngắn ≤ 2.000 ký tự; mỗi ô Năng lực đội ≤ 2.000 ký tự; tóm tắt kinh nghiệm mỗi người ≤ 500 ký tự. Công cụ đếm
ký tự dựa vào đúng tên các tiêu đề `##` bên dưới, xin đừng đổi tên.

## Tên giải pháp

CTCV – Cầm Tay Chỉ Việc: trợ lý thủ tục hành chính có kiểm chứng, giúp người dân tự làm được thủ tục, chạy hoàn toàn trên hạ tầng trong nước

## Mô tả ngắn

Vấn đề: thủ tục hành chính đã lên mạng, nhưng nhiều người dân, nhất là người cao tuổi và người ít quen công nghệ, vẫn không biết cần giấy tờ gì, nộp ở đâu, mất bao nhiêu tiền. Chatbot trả lời tự do có thể bịa số tiền hay thời hạn. Dùng mô hình AI nước ngoài thì câu hỏi của người dân bị đưa ra ngoài lãnh thổ. Bộ phận một cửa vẫn phải giải thích lại từng hồ sơ thiếu.

Giải pháp: CTCV là trợ lý thủ tục hành chính có kiểm chứng, bám đề DA940-01. Dữ liệu là lõi. Đội thu thập các trang thủ tục công khai trên Cổng Dịch vụ công Bộ Công an (tôn trọng robots, ghi mã băm sha256 và ngày lấy), rồi chuẩn hóa thành bản ghi có cấu trúc: thành phần hồ sơ, phí, thời hạn, căn cứ pháp lý. Kho hiện có {{eval:suites.qa.details.kb.procedures|chưa đo}} thủ tục. Chỉ mục lai (BM25 và bge-m3) tìm đúng thủ tục. Mô hình mở Qwen3.5-2B (bản lượng tử Q8_0) chạy cục bộ viết một câu từ đoạn nguồn. Lớp kiểm chứng buộc mọi con số phải có trong nguồn, đúng đơn vị; không đạt thì dùng câu mẫu từ dữ liệu có cấu trúc; không đủ căn cứ thì nói "cháu chưa chắc" và mời người thật hỗ trợ. Người dân hỏi bằng lời thường (câu gõ không dấu mới đúng {{eval:suites.qa.details.per_kind.no_diacritics.ok|chưa đo}}/{{eval:suites.qa.details.per_kind.no_diacritics.n|chưa đo}}), nhận câu trả lời ngắn, nút "Nguồn" dẫn về trang gốc và thẻ giấy tờ cần chuẩn bị. Cán bộ một cửa có màn đối chiếu hồ sơ: đánh dấu giấy tờ đã nhận, hệ thống liệt kê giấy tờ còn thiếu kèm nguồn, không dùng mô hình ngôn ngữ. Hệ thống không lưu CCCD, OTP hay mật khẩu, và không có công cụ nào thao tác trên tài khoản thật.

Giá trị: chạy hoàn toàn trên máy cục bộ, không gọi API nước ngoài. Số đo thật trên bộ kiểm thử nghiệp vụ: tỷ lệ tìm đúng thủ tục (recall@5) {{eval:suites.qa.metrics.recall_at_5|chưa đo}} %; câu mô hình viết lệch nguồn {{eval:ablation.modes.llm_unverified.hallucination|chưa đo}} % khi chưa kiểm, {{eval:suites.qa.metrics.hallucination|chưa đo}} % sau lớp kiểm chứng (chấm bằng chính tiêu chí của lớp này); độ trễ p95 {{eval:suites.qa.metrics.latency_p95_s|chưa đo}} giây trên laptop có GPU rời ({{eval:env.latency_s.cpu_only.p95|chưa đo}} giây khi chỉ dùng CPU). Mục tiêu vòng 2: mở rộng sang CSDL thủ tục hành chính quốc gia, cảnh báo hiệu lực văn bản, điền mẫu có đồng ý mà không lưu dữ liệu, đánh giá mô hình nền tiếng Việt trong nước.

## Năng lực đội

Bốn ô trên form, mỗi ô ≤ 2.000 ký tự. Anh/chị tự điền; chỉ ghi điều có thật và kiểm chứng được. Không ghi số điện
thoại, email hay số giấy tờ tùy thân.

### Lĩnh vực chuyên môn

[Chọn trên form trong các ô: AI/ML, UX/UI, Big Data, IoT, Blockchain, Cloud, Mobile, Cybersecurity, Web, Khác. Gợi ý
theo sản phẩm hiện có: AI/ML, Web, Cybersecurity; chỉ đánh dấu lĩnh vực đội thật sự làm.]

### Công nghệ thành thạo

[Anh/chị điền. Công nghệ repo đang dùng, chỉ giữ cái đội thật sự thành thạo: Python, FastAPI, Pydantic, React,
TypeScript, Tailwind, Playwright, Ollama/llama.cpp, BAAI/bge-m3, Qwen3.5-2B, BM25, Docker Compose, pytest. Công cụ AI
hỗ trợ viết mã: Claude Code (kê khai rõ trong bản đề xuất).]

### Kinh nghiệm làm việc nhóm

[Anh/chị điền: đội làm chung bao lâu, chia việc thế nào, dùng công cụ gì (GitHub, review mã, nhật ký công việc).]

### Thành tích

[Anh/chị điền: giải thưởng, dự án, bài báo có link kiểm chứng. Không ghi "đã triển khai" hay "đã thí điểm" cho CTCV
khi chưa có.]

## Tóm tắt kinh nghiệm từng thành viên

Mỗi người ≤ 500 ký tự, gõ trực tiếp trên form. Mẫu (thay phần trong ngoặc vuông):

### Mẫu

[Họ tên], [trình độ, ví dụ: sinh viên năm … ngành …, trường …]. Vai trò trong đội: [ví dụ: trưởng nhóm, phụ trách dữ
liệu và đánh giá]. Kinh nghiệm: [một vài dự án liên quan, công nghệ đã dùng]. Phần đóng góp cho CTCV: [ví dụ: pipeline
thu thập và chuẩn hóa thủ tục hành chính; bộ kiểm thử; giao diện cán bộ]. Link: [GitHub hoặc portfolio].

### Thành viên 1

[điền theo mẫu]

### Thành viên 2

[điền theo mẫu]

### Thành viên 3

[điền theo mẫu]
