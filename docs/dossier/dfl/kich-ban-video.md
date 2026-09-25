# Kịch bản video giới thiệu CTCV – Data for Life 2026 (đề DA940-01)

Video dài tối đa 3 phút, 1920×1080, phụ đề tiếng Việt in cứng vào hình, không nhạc. Nguồn máy đọc:
`video/loi-thoai.yaml` (phụ đề, thứ tự đoạn, thời lượng slide). File này dành cho người quay và người thu lời
thuyết minh. Hai file phải khớp nhau: sửa một file thì sửa luôn file kia.

## Luật quay (Thể lệ, Điều 7 và 13)

- **Chỉ quay phần chạy thật.** Mỗi bước demo có assert Playwright trên stack thật: API và Ollama chạy cục bộ,
  không `page.route`, không mock, không dữ liệu dựng sẵn. Bước nào lỗi thì dừng và báo gói chủ. Không quay lại
  bằng dữ liệu giả, không ghép cảnh từ lần chạy khác mà không ghi rõ.
- **Không cắt để giấu thời gian chờ.** Nếu phải tua nhanh đoạn chờ mô hình thì trên hình phải có chữ
  "tua nhanh". Có thể gọi làm nóng mô hình một lần trước khi quay (không nằm trong video); đó không phải mock.
- **Không giọng nói nhân tạo.** Lời thuyết minh là tùy chọn: người trong đội tự thu rồi ghép bằng `--voice`.
- **Không để lộ bí mật.** Ô mật khẩu dạng password. URL có mã lớp (`?lop=…`) không nằm trong khung hình.
  Không quay `.env`, terminal có biến môi trường hay thông tin cá nhân.
- **Không có số liệu tự viết.** Số chỉ xuất hiện trên slide 04 và 05, đọc tự động từ `eval/reports/latest.json`
  và `eval/reports/ablation-tthc.json`. Chưa có số thì slide ghi "chưa đo".
- **Không nói điều chưa có.** Không nói hay viết rằng sản phẩm đang được một cơ quan hay địa phương nào sử dụng.
  Giọng nói, sandbox có màn hình, điền tờ khai và thí điểm chỉ xuất hiện trên slide 06, ghi rõ là KẾ HOẠCH VÒNG 2.
- **Không hình người thật.** Cảnh minh họa vẽ bằng HTML.
- **Không dùng ảnh cũ.** Ảnh trong `docs/screens/` chụp với API giả lập (có chữ "dữ liệu thử"), không dùng cho
  video hay hình của bản đề xuất.
- **Trích đề đúng nguyên văn.** Dùng "…" khi lược bớt. Không trích câu "hàng chục triệu người dân cần được
  hướng": trên trang gốc câu này bị cắt dở, thêm chữ vào là sửa lời của đề.
- **Không nói quá về chủ quyền.** Chỉ nói "chạy trên máy cục bộ" và đọc danh sách máy chủ đã gọi từ báo cáo;
  trọng số mô hình được tải về một lần lúc cài đặt.

## Dòng thời gian (bản v2 đã dựng: 2:23, tức 143,3 giây; mốc lấy từ `ctcv-dfl-2026.srt` và `timeline.json`)

| # | Thời điểm | Đoạn (`id`) | Hình ảnh | Phụ đề (in cứng) |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:16 | `s01-van-de` (slide 01) | Trích nguyên văn mục tiêu DA940-01 ("đạt độ chính xác kiểm chứng được… hạ tỷ lệ ảo giác dưới ngưỡng cho phép"). Người cao tuổi đứng ở quầy một cửa, vẽ bằng HTML | DA940-01: "độ chính xác kiểm chứng được… / hạ tỷ lệ ảo giác dưới ngưỡng cho phép" |
| 2 | 0:16–0:28 | `s02-giai-phap` (slide 02) | Câu định vị và nhãn đề DA940-01 | CTCV: trợ lý thủ tục có kiểm chứng, / chạy trên máy cục bộ, không gọi API ngoài |
| 3 | 0:28–0:39 | `d01-hoi-phi` | Màn "Hỏi thủ tục". Gõ chậm "Đăng ký thường trú mất bao nhiêu tiền?", bấm nút xanh "Hỏi". Màn chờ "Cháu đang tìm trong giấy tờ chính thức…". Câu trả lời tối đa 2 câu | Hỏi mức phí đăng ký thường trú, / chạy thật trên laptop cá nhân, không mock |
| 4 | 0:39–0:45 | `d02-mo-nguon` | Bấm nút xanh "Nguồn". Bảng nguồn: tên thủ tục, "Nguồn: Cổng Dịch vụ công - Bộ Công an", "Lấy ngày …", đoạn trích, liên kết trang gốc | Nút Nguồn: cổng nguồn, ngày lấy dữ liệu, / đoạn trích và đường dẫn trang gốc |
| 5 | 0:45–0:57 | `d03-hoi-giay-to` | Hỏi "Làm căn cước cho cháu 14 tuổi cần mang giấy tờ gì?". Thẻ "Giấy tờ cần chuẩn bị" có ô đánh dấu, bản chính, bản sao | Thẻ "Giấy tờ cần chuẩn bị": đánh dấu / từng tờ, ghi rõ bản chính, bản sao |
| 6 | 0:57–1:04 | `d04-hoi-ngoai-kho` | Hỏi "Thủ tục đăng ký kết hôn cần những gì?". Hộp vàng "chưa chắc", mời cán bộ một cửa hoặc tình nguyện viên | Thủ tục chưa có trong kho: không bịa, / nói chưa chắc và chuyển người thật |
| 7 | 1:04–1:11 | `d05-hoi-otp` | Hỏi "Có người xưng công an gọi xin mã OTP, tôi có đọc không?". Hộp từ chối với câu an toàn cố định | Hỏi về mã OTP: trả câu an toàn cố định, / nhắc không đọc mã cho bất kỳ ai |
| 8 | 1:11–1:16 | `d06-can-bo-dang-nhap` | Vào `#can-bo`, đăng nhập tài khoản demo; mật khẩu hiện dấu chấm | Màn cán bộ một cửa, đăng nhập / bằng tài khoản demo |
| 9 | 1:16–1:22 | `d07-can-bo-tim` | Tìm "đăng ký tạm trú"; hiện danh mục thành phần hồ sơ | Tìm "đăng ký tạm trú": hiện danh mục / thành phần hồ sơ theo trường hợp |
| 10 | 1:22–1:28 | `d08-can-bo-danh-dau` | Đánh dấu mọi giấy tờ trừ một mục | Cán bộ đánh dấu các giấy tờ / người dân đã nộp |
| 11 | 1:28–1:33 | `d09-can-bo-ket-qua` | Bấm "Kiểm tra hồ sơ": danh sách còn thiếu màu đỏ, tin nhắn tối đa 2 câu soạn sẵn kèm nút "Sao chép tin nhắn", nguồn | Giấy tờ còn thiếu, tin nhắn soạn sẵn để / cán bộ sao chép; không dùng mô hình AI |
| 12 | 1:33–1:43 | `s03-kien-truc` (slide 03) | Sơ đồ bảy lớp: guardrail → truy xuất lai → cổng tin cậy → composer không có tool → kiểm chứng → câu mẫu → escalate | Guardrail, truy xuất lai, cổng tin cậy, / kiểm chứng số, không chắc thì chuyển |
| 13 | 1:43–1:57 | `s04-du-lieu` (slide 04) | Pipeline: crawl tôn trọng robots → manifest sha256 → bản ghi có schema → chỉ mục lai → lớp kiểm chứng. Số thủ tục, số đoạn, số lĩnh vực đọc từ `latest.json` | Dữ liệu là lõi: tôn trọng robots, mã băm / sha256, bản ghi có schema, bộ kiểm thử |
| 14 | 1:57–2:13 | `s05-so-lieu` (slide 05) | recall@5, answer_accuracy, refusal_accuracy; tỷ lệ câu mô hình viết lệch nguồn bị lớp kiểm chứng chặn (không ghi "ảo giác ≈ 0" cho chế độ có kiểm chứng: con số đó thấp do thiết kế, xem mục 6 bản đề xuất); p50/p95 đo trên laptop có GPU rời RTX 4050 (`env-tthc.json`); danh sách máy chủ ứng dụng đã gọi khi đánh giá. Chưa có số thì ghi "chưa đo" | Số đo trên laptop có GPU, đọc từ báo cáo; / chưa có số thì ghi "chưa đo" |
| 15 | 2:13–2:23 | `s06-lo-trinh` (slide 06) | Nhãn "KẾ HOẠCH VÒNG 2": bộ lỗi cài sẵn cho lớp kiểm chứng, mở rộng CSDL TTHC, cảnh báo hiệu lực, đánh giá mô hình nền tiếng Việt, thử khả dụng tại một xã, điền mẫu có đồng ý và không lưu, giọng nói PhoWhisper. Tên đội | Kế hoạch vòng 2: thêm dữ liệu, hiệu lực, / mô hình tiếng Việt, thử tại một xã |

Dấu `/` trong cột phụ đề là chỗ xuống dòng. Thời lượng thật của bản v2: slide 78 giây, demo 65,3 giây (9 bước,
quay liền trên hệ thống thật, không tua nhanh), tổng 143,3 giây (ffprobe). Dự kiến ban đầu là demo 97 giây, tổng
175 giây.
Nếu `timeline.json` cho thấy demo dài hơn 97 giây, xử lý theo thứ tự: (1) rút thời lượng slide, mỗi slide không
dưới 8 giây; (2) tua nhanh đoạn chờ mô hình, có chữ "tua nhanh" trên hình; (3) báo orchestrator. Không cắt câu
trả lời, và không thay bằng dữ liệu dựng sẵn.

## Lời thuyết minh (tùy chọn, người trong đội tự thu)

Đọc chậm, giọng tự nhiên, khoảng 2 từ mỗi giây. Không nêu con số nào ngoài số đang hiện trên slide.

1. **Slide 01.** "Thủ tục hành chính đã lên mạng, nhưng nhiều người cao tuổi vẫn chưa biết cần giấy tờ gì. Đề
   DA940-01 đòi độ chính xác kiểm chứng được và tỷ lệ ảo giác dưới ngưỡng."
2. **Slide 02.** "CTCV là trợ lý thủ tục có kiểm chứng, chạy trên máy cục bộ, không gọi API bên ngoài."
3. **Demo phí.** "Bác hỏi mức phí đăng ký thường trú. Trợ lý tìm trong dữ liệu của Cổng Dịch vụ công Bộ Công an
   rồi trả lời tối đa hai câu."
4. **Nguồn.** "Bấm nút Nguồn để xem trang gốc và ngày lấy dữ liệu."
5. **Giấy tờ.** "Hỏi giấy tờ làm căn cước cho cháu mười bốn tuổi. Trợ lý hiện danh sách để bác đánh dấu từng tờ."
6. **Ngoài kho.** "Thủ tục chưa có trong kho thì trợ lý không bịa, mà nói chưa chắc và mời người thật hỗ trợ."
7. **OTP.** "Câu hỏi về mã OTP luôn nhận lời nhắc an toàn cố định."
8. **Cán bộ (đoạn 8–11).** "Ở bộ phận một cửa, cán bộ đánh dấu giấy tờ đã nhận. Hệ thống liệt kê giấy tờ còn
   thiếu và soạn sẵn tin nhắn để cán bộ sao chép gửi người dân, kèm nguồn."
9. **Slide 03.** "Mọi câu trả lời đi qua cổng tin cậy và lớp kiểm chứng số."
10. **Slide 04.** "Dữ liệu là lõi: thu thập tôn trọng robots, có mã băm, có schema và bộ kiểm thử."
11. **Slide 05.** "Đây là số đo thật trên laptop có GPU rời, đọc tự động từ báo cáo đánh giá."
12. **Slide 06.** "Vòng 2, đội sẽ đo lớp kiểm chứng bằng bộ lỗi cài sẵn, mở rộng dữ liệu, cảnh báo hiệu lực văn
    bản, đánh giá mô hình tiếng Việt và thử khả dụng tại một xã."

## Quay và ghép

1. Quay demo trên stack thật (gói P13, không chạy cùng lúc với lượt đánh giá):
   `uv run python scripts/dev_cpu.py --run pnpm -C apps/web exec playwright test -c e2e/demo/playwright.demo.config.ts record-demo`.
2. Sau khi có `eval/reports/latest.json` và `ablation-tthc.json`: sinh hình và slide bằng `figures.demo`.
3. Ghép: `uv run python docs/dossier/dfl/video/make_video.py`, thêm `--voice <file>` nếu có lời thu âm.
4. Kiểm tra: thời lượng tối đa 180 giây (ffprobe), 1920×1080, phụ đề đọc được. Khung hình đăng nhập không lộ mật khẩu
   hay mã lớp. Mỗi đoạn tua nhanh đều có chữ "tua nhanh".
5. Tải lên YouTube (chế độ Không công khai) hoặc Google Drive (ai có đường liên kết đều xem được). Mở thử bằng cửa
   sổ ẩn danh, rồi ghi link vào `docs/dossier/private/team-dfl.yaml` (`lien_ket.video`).

## Trạng thái (25/9/2026, bản v2)

- Bản v2: `docs/dossier/out/dfl/v2/video/ctcv-dfl-2026.mp4`. Dài 143,3 giây, 1920×1080, H.264, 30 khung/giây,
  4.614.380 byte. Phụ đề tiếng Việt in cứng trong dải tối ở đáy khung hình; có thêm file `.srt` gồm 15 đoạn. Không có
  lời thuyết minh.
- Quay lại trên hệ thống thật với mã v2: 9 bước đều có assert trên API thật, không mock, không `page.route`.
  Bước `d07-can-bo-tim` nay qua vì màn cán bộ gọi lại API khi chọn trường hợp (bản quay lúc 10:30 dừng ở bước này).
- Slide 05 đọc số của lượt đo v2 (`latest.json` lúc 2026-09-25T07:34:35Z), tiêu đề ghi "GPU RTX 4050 Laptop".
- Bản v1 (134,3 giây, `docs/dossier/out/dfl/video/`) giữ nguyên, không ghi đè.
- Tấm ảnh ghép 12 khung (`v2/video/contact-sheet.jpg`) đã được xem bằng mắt: chữ tiếng Việt có dấu hiện đủ, phụ đề
  nằm trong dải tối. Chưa có người xem hết video ở tốc độ thường; việc này người dùng làm trước khi tải lên.
