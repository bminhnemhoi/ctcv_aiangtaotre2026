# Lời thuyết minh cho video v2 (dùng với Vbee AI)

Video: `docs/dossier/out/dfl/v2/video/ctcv-dfl-2026.mp4` (143,3 giây, 15 cảnh). Mốc thời gian lấy từ
`docs/dossier/out/dfl/v2/video/ctcv-dfl-2026.srt`. Mỗi đoạn viết để đọc vừa khung giờ của cảnh ở tốc độ đọc bình thường
(khoảng 3,3 âm tiết/giây, chừa lề đầu và cuối). Chữ số đã viết thành chữ, không dùng viết tắt, để giọng máy đọc đúng.
Mọi thông tin trong lời đọc khớp với hồ sơ và số đo thật (`eval/reports/latest.json`, lượt đo v2).

## Cách tạo giọng trên Vbee

1. Chọn một giọng đọc tin tức hoặc kể chuyện, rõ ràng, tốc độ 1.0. Dùng cùng một giọng cho cả 15 đoạn.
2. **Tạo 15 file riêng**, mỗi đoạn một file, đặt tên `01.mp3` … `15.mp3` theo số thứ tự bên dưới, rồi để chung một thư
   mục. Ghép từng đoạn đúng mốc thời gian sẽ khớp hình tốt hơn nhiều so với một file dài.
3. Nghe lại các đoạn có chữ dễ đọc sai: "O-T-P", "Cầm Tay Chỉ Việc", "Bộ Công an". Nếu Vbee đọc "O-T-P" chưa đúng thì
   thay bằng "ô tê pê".
4. Nếu một đoạn dài hơn cột "Tối đa", tăng tốc độ lên 1.1 cho riêng đoạn đó (không cắt chữ).
5. Gửi thư mục 15 file cho orchestrator (Claude Code) để ghép vào video. Mỗi đoạn được đặt đúng mốc bắt đầu, trễ 0,3
   giây, rồi dựng lại mp4 bằng `make_video.py --voice`.

## Lời đọc theo cảnh

| # | Mốc | Tối đa | Cảnh trên hình | Lời đọc |
| --- | --- | --- | --- | --- |
| 01 | 0:00–0:16 | 15 s | Slide "Vấn đề" | Thủ tục hành chính đã lên mạng, nhưng nhiều người dân, nhất là người cao tuổi, vẫn không rõ cần giấy tờ gì, mất bao nhiêu tiền. Đề án chín trăm bốn mươi đặt yêu cầu: trợ lý phải có độ chính xác kiểm chứng được. |
| 02 | 0:16–0:28 | 11 s | Slide "Giải pháp" | Cầm Tay Chỉ Việc là trợ lý thủ tục có kiểm chứng. Mọi thứ chạy trên máy trong nước, không gửi câu hỏi của người dân ra nước ngoài. |
| 03 | 0:28–0:39 | 10 s | Hỏi phí đăng ký thường trú | Bác hỏi phí đăng ký thường trú. Trợ lý trả lời: hai mươi nghìn đồng nếu nộp trực tiếp, mười nghìn nếu nộp trực tuyến. |
| 04 | 0:39–0:44 | 5 s | Bấm nút Nguồn | Bấm nút Nguồn để xem trang gốc và ngày lấy dữ liệu. |
| 05 | 0:44–0:56 | 11 s | Thẻ giấy tờ (căn cước cho cháu 14 tuổi) | Hỏi làm căn cước cho cháu mười bốn tuổi, trợ lý hiện thẻ Giấy tờ cần chuẩn bị, ghi rõ bản chính, bản sao để bác đánh dấu. |
| 06 | 0:56–1:04 | 7 s | Hỏi thủ tục chưa có trong kho | Thủ tục chưa có trong kho, trợ lý không bịa, mà nói chưa chắc và mời người thật. |
| 07 | 1:04–1:10 | 6 s | Hỏi về mã OTP | Ai xin mã O-T-P, trợ lý nhắc bác không đọc cho bất kỳ ai. |
| 08 | 1:10–1:16 | 5 s | Cán bộ đăng nhập | Phía cán bộ một cửa đăng nhập vào màn đối chiếu hồ sơ. |
| 09 | 1:16–1:22 | 5 s | Tìm "đăng ký tạm trú" | Tìm thủ tục đăng ký tạm trú, chọn đúng trường hợp của người dân. |
| 10 | 1:22–1:27 | 5 s | Đánh dấu giấy tờ | Đánh dấu những giấy tờ người dân đã nộp. |
| 11 | 1:27–1:33 | 5 s | Kết quả đối chiếu | Hệ thống báo giấy tờ còn thiếu và soạn sẵn tin nhắn. |
| 12 | 1:33–1:43 | 9 s | Slide "Kiến trúc" | Mỗi câu hỏi đi qua bảy lớp: chặn thông tin nhạy cảm, tìm đúng thủ tục, kiểm từng con số với nguồn; không chắc thì chuyển người thật. |
| 13 | 1:43–1:57 | 13 s | Slide "Dữ liệu là lõi" | Dữ liệu là lõi: một trăm lẻ bảy thủ tục lấy hợp lệ từ Cổng Dịch vụ công Bộ Công an, mỗi bản ghi có mã băm và chuẩn hóa theo cấu trúc chung, kèm bộ kiểm thử mở. |
| 14 | 1:57–2:13 | 15 s | Slide "Số liệu" | Trên một trăm ba mươi tám câu kiểm thử, tự chấm: mọi câu trả lời đều có trích dẫn hỗ trợ, không câu nào lệch nguồn sau kiểm chứng, tám mươi sáu phần trăm đúng thủ tục và đủ dữ kiện. |
| 15 | 2:13–2:23 | 9 s | Slide "Kế hoạch vòng 2" | Vòng hai, đội sẽ mở rộng dữ liệu, cảnh báo hiệu lực văn bản, đánh giá mô hình tiếng Việt và thử nghiệm tại một xã. |

## Bản liền mạch (chỉ để đọc duyệt, không dùng để ghép)

Thủ tục hành chính đã lên mạng, nhưng nhiều người dân, nhất là người cao tuổi, vẫn không rõ cần giấy tờ gì, mất bao
nhiêu tiền. Đề án chín trăm bốn mươi đặt yêu cầu: trợ lý phải có độ chính xác kiểm chứng được.

Cầm Tay Chỉ Việc là trợ lý thủ tục có kiểm chứng. Mọi thứ chạy trên máy trong nước, không gửi câu hỏi của người dân ra
nước ngoài.

Bác hỏi phí đăng ký thường trú. Trợ lý trả lời: hai mươi nghìn đồng nếu nộp trực tiếp, mười nghìn nếu nộp trực tuyến.
Bấm nút Nguồn để xem trang gốc và ngày lấy dữ liệu. Hỏi làm căn cước cho cháu mười bốn tuổi, trợ lý hiện thẻ Giấy tờ
cần chuẩn bị, ghi rõ bản chính, bản sao để bác đánh dấu. Thủ tục chưa có trong kho, trợ lý không bịa, mà nói chưa chắc
và mời người thật. Ai xin mã O-T-P, trợ lý nhắc bác không đọc cho bất kỳ ai.

Phía cán bộ một cửa đăng nhập vào màn đối chiếu hồ sơ. Tìm thủ tục đăng ký tạm trú, chọn đúng trường hợp của người dân.
Đánh dấu những giấy tờ người dân đã nộp. Hệ thống báo giấy tờ còn thiếu và soạn sẵn tin nhắn.

Mỗi câu hỏi đi qua bảy lớp: chặn thông tin nhạy cảm, tìm đúng thủ tục, kiểm từng con số với nguồn; không chắc thì
chuyển người thật. Dữ liệu là lõi: một trăm lẻ bảy thủ tục lấy hợp lệ từ Cổng Dịch vụ công Bộ Công an, mỗi bản ghi có
mã băm và chuẩn hóa theo cấu trúc chung, kèm bộ kiểm thử mở.

Trên một trăm ba mươi tám câu kiểm thử, tự chấm: mọi câu trả lời đều có trích dẫn hỗ trợ, không câu nào lệch nguồn sau
kiểm chứng, tám mươi sáu phần trăm đúng thủ tục và đủ dữ kiện. Vòng hai, đội sẽ mở rộng dữ liệu, cảnh báo hiệu lực văn
bản, đánh giá mô hình tiếng Việt và thử nghiệm tại một xã.
