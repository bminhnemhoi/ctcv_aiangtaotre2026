# Yêu cầu cuộc thi Data for Life mùa 4 (2026), đề DA940-01

Ghi nhận ngày 25/9/2026 (khoảng 01:45–03:00 giờ Việt Nam). Nguồn chính: dataforlife.vn (tải HTML gốc bằng curl,
trích văn bản); nguồn phụ: báo chí và cổng của Bộ Công an. Phần đặt trong khối trích dẫn (`>`) là **chép nguyên
văn**; phần còn lại là tóm tắt hoặc phân tích của đội. Các con số trích từ báo chí đều ghi rõ nguồn; không có số
nào do đội tự ước lượng mà không ghi "giả định" hoặc "mục tiêu".

> Thay đổi ưu tiên: người dùng quyết định dự thi Data for Life 2026 thay cho cuộc thi Sáng tạo trẻ AI 2026
> (`docs/competition/BTC-2026-yeu-cau.md` không còn là ưu tiên). CLAUDE.md vẫn ghi BTC-2026 là nguồn sự thật về
> hồ sơ. Sửa CLAUDE.md là điểm dừng bắt buộc (chỉ qua ADR), nên cần một ADR ghi nhận việc chuyển cuộc thi.

## 0. Tóm tắt để hành động ngay

| Hạng mục | Nội dung |
| --- | --- |
| Hạn nộp cứng | **25/09/2026**, ghi trên form nộp (`/submission`, `/overview`, `/pick-idea`) và trang `/tham-gia-cuoc-thi`. Không ghi giờ, nên nộp xong trong ngày làm việc, không chờ đến 23:59 |
| Hồ sơ bắt buộc | Phiếu đăng ký online; bản đề xuất ≤ 10 trang, PDF; video ≤ 3 phút (dạng link); cam kết có chữ ký của mọi thành viên (trên form là ô gõ tên từng người); link dùng thử không bắt buộc |
| Giới hạn trên form | Tên giải pháp ≤ 400 ký tự; mô tả ngắn ≤ 2.000 ký tự; tệp đề xuất ≤ 10 MB (form nhận doc/docx/pdf/ai/xlsx/xls, nhưng thể lệ quy định PDF, sai định dạng thì hồ sơ không hợp lệ, nên **nộp PDF**) |
| Mẫu đề xuất chính thức | **Không tìm thấy.** Link "PDF tiếng Việt / PDF Tiếng Anh" trên trang thể lệ đều trỏ tới `#`. Không có mẫu tải về, không có trang Q&A |
| Tiêu chí | 5 tiêu chí cốt lõi (Điều 9), **không công bố trọng số**. Chọn đề trong Ngân hàng ý tưởng được **cộng điểm ưu tiên**; đề tự đề xuất không được cộng ở vòng hồ sơ |
| Đề nên chọn trên form | Hướng "Bài toán Cơ quan nhà nước", đề **DA940-01** (Đề án 940, Bộ Công an). Lý do ở mục 5.1 |
| Góc để thắng | Không làm thêm một chatbot tra cứu thủ tục, vì VNeID đã có. Định vị: **trợ lý có kiểm chứng giúp người dân tự làm được thủ tục**, gồm RAG thủ tục hành chính (TTHC) có dẫn chiếu điều khoản và hiệu lực, cơ chế "không chắc thì chuyển người thật", sandbox luyện thao tác, giọng nói cho người cao tuổi, chạy hoàn toàn trong nước (mục 5.2) |
| Rủi ro lớn nhất | Bị xem là "chatbot TTHC thứ N"; chưa có kho tri thức và số đo thật; mô hình nền Qwen không phải "mô hình nền tiếng Việt trong nước"; bất biến 2 (không dùng dữ liệu định danh) có vẻ mâu thuẫn với yêu cầu "điền biểu mẫu từ dữ liệu định danh" (mục 5.5) |

## 1. Thông tin cuộc thi

### 1.1 Tổ chức, chủ đề, định vị

> Tên cuộc thi: Cuộc thi quốc tế "Data for Life" - Mùa 4 (2026)". Chủ đề: "Build Together" - cùng kiến tạo giải
> pháp công nghệ vì lợi ích cộng đồng. Định vị: cuộc thi theo mô hình ươm tạo và tăng tốc giải pháp dữ liệu với
> chất liệu là các bài toán thực tiễn. Đội thi mang tới một ý tưởng hoặc sản phẩm ở giai đoạn sớm, cùng đội ngũ
> cố vấn và đơn vị chủ quản đặt đề bài để phát triển giải pháp đáp ứng nhu cầu thực tiễn, hướng tới cơ hội được
> triển khai thí điểm hoặc tiếp cận với thị trường. — Thể lệ, Điều 1

> Phát hiện, ươm tạo và tăng tốc các giải pháp dữ liệu phục vụ chính phủ số, kinh tế số, xã hội số theo tinh thần
> Nghị quyết số 57-NQ/TW và Đề án 06. — Thể lệ, Điều 2

- Chủ trì: Bộ Công an, đầu mối là Cục Cảnh sát QLHC về TTXH (C06). Trưởng Ban Tổ chức là Thiếu tướng Vũ Văn Tấn,
  Cục trưởng C06.
- Đơn vị phối hợp: Bộ KH&CN, Bộ GD&ĐT, ĐH Bách khoa Hà Nội, VTV, Block71 Việt Nam (NUS). Lễ phát động ở Singapore
  có AI Singapore tham gia.
- Căn cứ tổ chức: Kế hoạch 398/KH-BCA-C06 ngày 21/5/2026. Ban Tổ chức, Ban Giám khảo và Ban Cố vấn được thành lập
  theo QĐ 5203/QĐ-BCA ngày 17/8/2026 (VJST).
- **Điểm mới của mùa 4** (Đại biểu Nhân dân, 28/8/2026):
  - cuộc thi gắn trực tiếp với các bài toán triển khai QĐ 940/QĐ-TTg (Đề án phát triển VNeID 2026–2030);
  - từ vòng bán kết, các sáng kiến được xác thực sẽ được đưa lên Cổng Sáng kiến quốc gia do Bộ KH&CN quản trị;
  - C06, ĐH Bách khoa và một số doanh nghiệp dựng phòng lab hỗ trợ các đội trước vòng chung kết;
  - tư duy tổ chức chuyển từ "thi ý tưởng" sang "tìm kiếm, phát triển giải pháp có khả năng triển khai thực tế".
- Phát biểu cần nhớ của Trưởng BTC tại lễ phát động 28/8: *"yêu cầu quan trọng của chuyển đổi số là phải đưa công
  nghệ đến gần người dân… cần đặc biệt chú trọng nâng cao kỹ năng số cho người dân"* (Đại biểu Nhân dân). Câu này
  trùng với cốt lõi của CTCV.
- Quy mô cạnh tranh các mùa trước:
  - mùa 1 (2023): 198 sản phẩm;
  - mùa 2 (2024): 376 ý tưởng, hơn 800 thí sinh;
  - mùa 3 (2025): hơn 2.600 đội và 9.100 thí sinh theo C06 (CafeF ghi khoảng 2.900 đội). 60 đội qua vòng hồ sơ,
    30 đội vào triển lãm. Tỷ lệ qua vòng 1 vào khoảng 2–3 %.
  - Mùa 4 có hơn 5.000 ý tưởng trong Ngân hàng ý tưởng (VTV, VTC).

### 1.2 Mốc thời gian: các nguồn mâu thuẫn nhau

| Nguồn (truy cập 25/9/2026) | Vòng 1: tuyển chọn hồ sơ | Vòng 2: phát triển giải pháp | Vòng 3: triển lãm | Vòng 4: chung kết |
| --- | --- | --- | --- | --- |
| Thể lệ `/the-le` (Điều 8) | 15/8 – 20/9/2026 (chọn khoảng 60 đội) | 25/9 – 06/11/2026 (chọn khoảng 30 đội) | Đầu tháng 11/2026 (chọn 06 đội) | 20 – 25/11/2026 |
| Trang chủ `/` (Lộ trình) | **28/8/2026 – 25/9/2026** | 28/9/2026 – 25/10/2026 | Trung tuần tháng 11/2026, 03–05 ngày | 01 ngày, VTV ghi hình |
| Form `/submission`, `/overview`, `/pick-idea`, `/team-members` | "Hạn nộp: **25/09/2026**" | – | – | – |
| `/tham-gia-cuoc-thi` | "Thời hạn đăng ký: **25/09/2026**" | – | – | – |
| Công an Sơn La, Công an Cần Thơ (bài hưởng ứng) | 10/8/2026 – 15/9/2026 | – | – | – |

Thể lệ cho phép thay đổi lịch:

> Cuộc thi gồm 04 vòng, thời gian dự kiến như sau (Ban Tổ chức có thể điều chỉnh và thông báo công khai)

Kết luận:

- Coi **25/09/2026** là hạn cứng, vì hệ thống nộp hiện ghi mốc này và là mốc mới nhất.
- Không có thông báo gia hạn chính thức nào (tìm "gia hạn" không ra kết quả cho mùa 4).
- Ngày 20/9 trong thể lệ và ngày 15/9 trong các bài hưởng ứng là lịch cũ.
- Vòng 2 có thể bắt đầu ngay từ 25/9 hoặc từ 28/9, nên cần sẵn sàng làm MVP ngay sau khi nộp.

### 1.3 Đối tượng và cấu trúc đội

> Cuộc thi mở cho cá nhân và đội nhóm đến từ trong nước và quốc tế. […] Đội nhóm có tối đa 10 thành viên. Cá nhân
> được đăng ký độc lập; Ban Tổ chức hỗ trợ kết nối, ghép đội cho các cá nhân có nhu cầu. Người đại diện đội đủ 18
> tuổi tại thời điểm đăng ký, là đầu mối liên hệ với Ban Tổ chức. Mỗi cá nhân chỉ tham gia một đội; mỗi đội nộp
> một giải pháp dự thi. Không được dự thi: thành viên Ban Tổ chức, Ban Giám khảo, đội ngũ cố vấn, nhân sự trực tiếp
> vận hành cuộc thi và người thân trực hệ của giám khảo. — Thể lệ, Điều 4

- Mâu thuẫn về số thành viên. Phần đầu trang thể lệ và trang chủ ghi "Đội thi từ **03–10** thành viên". Điều 4 ghi
  "tối đa 10" và cho phép cá nhân. Form chỉ chặn tối đa (`MAX_MEMBERS = 10`), không chặn tối thiểu.
  **Khuyến nghị: đăng ký từ 3 thành viên trở lên** để tránh rủi ro và để có điểm ở tiêu chí năng lực đội ngũ.
- Người đại diện (đội trưởng) cần đủ 18 tuổi.
- Email khởi tạo hồ sơ không sửa được sau khi tạo. Cần nhớ cả tài khoản lẫn mật khẩu.

### 1.4 Hồ sơ dự thi và định dạng

> Hồ sơ dự thi nộp trực tuyến tại www.dataforlife.vn, gồm: Phiếu đăng ký trực tuyến (thông tin đội, thành viên,
> lĩnh vực, bài toán hướng tới); Bản đề xuất giải pháp (tối đa 10 trang, định dạng PDF); Video giới thiệu (tối đa
> 03 phút); Bản cam kết dự thi; Đường dẫn sản phẩm dùng thử (nếu có, không bắt buộc). Hồ sơ nộp sau thời hạn, thiếu
> thành phần bắt buộc hoặc sai định dạng được xem là không hợp lệ. — Thể lệ, Điều 6

> Đăng ký trực tuyến duy nhất tại địa chỉ www.dataforlife.vn. Người đại diện điền biểu mẫu và bổ sung thông tin của
> các thành viên, bao gồm thông tin về năng lực, trình độ của từng thành viên. Đội thi được lựa chọn giải một bài
> toán trong Ngân hàng ý tưởng khi đăng ký. Việc lựa chọn bài toán từ Bộ bài toán chuẩn hóa (Ngân hàng ý tưởng)
> được cộng điểm ưu tiên theo quy định tại Điều 8. — Thể lệ, Điều 5

### 1.5 Form nộp trực tuyến: 4 bước, trường và giới hạn

Đọc từ HTML và JS của form (`/team-members`, `/pick-idea`, `/submission`, `/js/Dashboard.js`). API
`/api/web/ContestTopic` cần đăng nhập, không đọc được.

| Bước | Trường (* = bắt buộc) | Giới hạn, ghi chú |
| --- | --- | --- |
| 1. Khởi tạo (`/khoi-tao-ho-so`) | Email đại diện (xác thực), mật khẩu | Không sửa được email; có trang `/preview` để xem hồ sơ trước khi gửi |
| 2. Đội và thành viên (`/team-members`) | Tên đội*; Trường/Tổ chức/Công ty; Khu vực* (Bắc/Trung/Nam/Quốc tế) | Tên đội ≤ 400 ký tự; tổ chức ≤ 400 ký tự |
| | Từng thành viên: Họ tên*, Ngày sinh* (dd/mm/yyyy), Email* (đội trưởng), SĐT* (9–12 số), Trình độ*, Vai trò*, Tóm tắt kinh nghiệm*, Link portfolio/GitHub/LinkedIn* | Tóm tắt ≤ 500 ký tự; đội trưởng bắt buộc có portfolio |
| | Năng lực đội: lĩnh vực chuyên môn (AI/ML, UX/UI, Big Data, IoT, Blockchain, Cloud, Mobile, Cybersecurity, Web, Khác); công nghệ thành thạo; kinh nghiệm làm việc nhóm; thành tích | Mỗi ô ≤ 2.000 ký tự; ô "khác" ≤ 500 ký tự |
| 3. Chọn đề (`/pick-idea`) | Hướng đề bài*: Bài toán Cơ quan nhà nước / Điểm nghẽn cộng đồng / Tự đề xuất; Nhóm chuyên môn/lĩnh vực*; Đề bài dự thi* (tìm theo mã hoặc tên) | Form ghi: "**Đề bài tự đề xuất không được xét cộng điểm tại Vòng Hồ sơ.**" Đề tự đề xuất có tên ≤ 500 ký tự, mô tả ≤ 2.000 ký tự |
| 4. Nộp hồ sơ (`/submission`) | Tên giải pháp*; Mô tả ngắn* ("vấn đề, giải pháp và giá trị nổi bật"); Bản đề xuất* (tệp); Thư cam kết (mỗi thành viên gõ chữ ký); Link video*; Link sản phẩm dùng thử | Tên ≤ 400; mô tả ≤ 2.000; tệp ≤ 10 MB (`10 * 1024 * 1024`); chữ ký ≤ 400 ký tự; video: "YouTube, Google Drive hoặc nền tảng lưu trữ video"; ngày cam kết tự lấy theo ngày gửi |

Thư cam kết trên form (nguyên văn):

> THƯ CAM KẾT THAM GIA CUỘC THI DATA FOR LIFE 2026. Chúng tôi, đội thi "[ Tên đội ]", cam kết: Tham gia đầy đủ các
> giai đoạn của cuộc thi "Data for Life 2026" nếu được chọn vào vòng trong. Tuân thủ các quy định về sở hữu trí tuệ
> và bảo mật dữ liệu trong suốt quá trình tham gia cuộc thi. Các thông tin khai báo trong hồ sơ này là chính xác và
> đầy đủ. Chúng tôi hoàn toàn chịu trách nhiệm về tính xác thực của những thông tin đã cung cấp. Sẵn sàng cung cấp
> thêm thông tin hoặc tham gia phỏng vấn nếu được Ban Tổ chức yêu cầu. Ngày _____ tháng _____ năm 2026. CHỮ KÝ CỦA
> TẤT CẢ THÀNH VIÊN TRONG ĐỘI

### 1.6 Yêu cầu giải pháp, sở hữu trí tuệ, dữ liệu, vi phạm

> Giải pháp thuộc một trong các lĩnh vực ưu tiên hoặc trực tiếp giải một bài toán trong Ngân hàng ý tưởng. Giải
> pháp phải có yếu tố dữ liệu là nội dung cốt lõi (thu thập, xử lý, phân tích, chia sẻ hoặc bảo vệ dữ liệu). Được
> phép sử dụng công cụ trí tuệ nhân tạo trong quá trình phát triển; nghiêm cấm làm giả kết quả trình diễn, số liệu
> thử nghiệm hoặc trình diễn tính năng không tồn tại. Đội thi tự chịu trách nhiệm về bản quyền mã nguồn, dữ liệu
> và tài nguyên sử dụng. — Thể lệ, Điều 7 (lĩnh vực ưu tiên đầu tiên: "Chính phủ số và dịch vụ công")

> Quyền sở hữu trí tuệ đối với giải pháp thuộc về đội thi […] Trong thời hạn 12 tháng kể từ khi kết thúc chung
> kết, cơ quan nhà nước (thông qua Ban Tổ chức) có quyền ưu tiên đàm phán hợp tác thí điểm, triển khai giải pháp
> đạt giải theo nguyên tắc thỏa thuận bình đẳng. Đội thi tuân thủ pháp luật về dữ liệu và bảo vệ dữ liệu cá nhân;
> chỉ sử dụng dữ liệu hợp pháp trong quá trình dự thi. — Điều 11

> Trường hợp phát hiện gian lận (sao chép, làm giả kết quả, sử dụng dữ liệu trái phép), Ban Tổ chức hủy kết quả,
> thu hồi giải thưởng và công bố công khai, kể cả sau khi đã trao giải. — Điều 13. Khiếu nại trong 05 ngày làm việc
> kể từ ngày công bố kết quả vòng. Đội không tự công bố kết quả trước BTC (Điều 12).

Hệ quả: câu "trình diễn tính năng không tồn tại" bị cấm. Video và bản đề xuất **chỉ được quay và mô tả những gì
chạy được**. Phần kế hoạch phải ghi rõ là "vòng 2" hoặc "mục tiêu".

### 1.7 Giải thưởng và hỗ trợ

| Giải | Giá trị (Điều 10) |
| --- | --- |
| Nhất (01) | 500.000.000 đ, kèm chuyến du lịch kết hợp hội thảo công nghệ |
| Nhì (02) | 100.000.000 đ/giải |
| Ba (03) | 50.000.000 đ/giải |
| Giải phụ | Sáng tạo nhất; Tác động xã hội; Công nghệ ấn tượng; Cộng đồng bình chọn |

- Tổng giải thưởng khoảng 1 tỷ đồng.
- Đội đạt giải được đàm phán thí điểm với cơ quan nhà nước, được kết nối nhà đầu tư và tổ chức ươm tạo.
- Hỗ trợ ở vòng 2, theo trang chủ: đào tạo, mentoring, hạ tầng công nghệ, môi trường thử nghiệm. Có lab tại Hà
  Nội, Đà Nẵng, TP.HCM; "API & dữ liệu mở có kiểm soát".

## 2. Tiêu chí chấm và ngụ ý cho bản đề xuất

> Mỗi vòng thi có bộ tiêu chí đánh giá riêng; giám khảo chấm độc lập trên phiếu điểm chuẩn hóa, kết quả được lưu
> vết phục vụ giải quyết khiếu nại và hậu kiểm. Các tiêu chí cốt lõi gồm: mức độ bám vấn đề thực tiễn; tính sáng
> tạo và tính mới; tính khả thi kỹ thuật và kiến trúc dữ liệu; tiềm năng tác động xã hội và thị trường; năng lực
> và cam kết của đội ngũ. Hội đồng Giám khảo vòng Chung kết gồm đại diện các đơn vị tổ chức và các chuyên gia độc
> lập. — Thể lệ, Điều 9

- **Không có trọng số công bố.** Phiếu điểm chuẩn hóa không được đăng công khai. Không tìm thấy thang điểm của mùa 3
  hay mùa 4.
- Mùa 3, hội đồng chọn 60 đội theo "tính khả thi, tính ứng dụng và ý nghĩa nhân văn" (C06).
- Mùa 1 (2023) chấm theo "kỹ thuật, khả năng thuyết trình và khả năng ứng dụng".
- Điểm cộng ưu tiên: áp cho đề trong Ngân hàng ý tưởng; đề tự đề xuất không được cộng.
- Mức cộng cho từng "Mức ưu tiên" của đề không được công bố. Form có hiển thị trường "Mức ưu tiên".

**Hội đồng các mùa trước đã coi trọng gì** (các nhận xét dưới đây là bằng chứng, không phải thể lệ):

| Mùa | Đội thắng, giải pháp | Nhận xét của BTC/BGK | Bài học cho CTCV |
| --- | --- | --- | --- |
| 2 (2024) | GoTrust: Kiosk MediPay, đã triển khai thật; người dân dùng CCCD tra lịch sử khám (Nhất, 300 triệu) | "Hầu hết các đội đều đã có sản phẩm hiện hữu, định vị đối tượng rõ ràng" (Đại tá Vũ Văn Tấn). Góp ý cho một đội: "cần kết nối thêm dữ liệu" để dữ liệu "đa chiều hơn". Giám khảo Data.gov.sg khen giải pháp "không cạnh tranh với bác sĩ… hỗ trợ" | Sản phẩm phải chạy thật; nối nhiều nguồn dữ liệu; AI hỗ trợ con người chứ không thay thế cán bộ hay tình nguyện viên |
| 3 (2025) | Cheppy: nền tảng học tiếng Anh cho tiểu học, gồm gia sư ảo, AI chấm phát âm, lọc nội dung an toàn, bản sắc văn hóa Việt (Nhất, 500 triệu) | BGK (ông Ngô Quốc Thái) khen "mức độ hoàn thiện và khả năng vận hành thực tế… phù hợp thị trường Việt Nam, quy mô lớn, nhu cầu rõ ràng". Việc cần làm tiếp: "mở rộng nguồn dữ liệu để nâng cao độ chính xác của mô hình AI, xây dựng chiến lược kinh doanh rõ ràng và tận dụng các cơ chế thử nghiệm có kiểm soát (sandbox)". BTC: năm 2025 "các đội thi bắt buộc phải có sản phẩm hoàn chỉnh… được kiểm chứng trực tiếp thông qua vòng triển lãm" | Mức hoàn thiện và trải nghiệm tại triển lãm quyết định. Người dùng đại chúng. An toàn nội dung. Sandbox được BGK nhắc đích danh |
| 4 (2026) | – | Trưởng BTC: "đưa công nghệ đến gần người dân… nâng cao kỹ năng số cho người dân"; "ý tưởng có người đồng hành, sản phẩm có nơi thử nghiệm và giải pháp được nhân rộng" | Bình dân học vụ số và sandbox của CTCV khớp đúng thông điệp của mùa 4 |

**Ngụ ý cho bản đề xuất ≤ 10 trang.** Trọng số dưới đây là **giả định** chia đều, để phân bổ số trang:

| Tiêu chí | Bằng chứng giám khảo cần thấy | Phân bổ đề xuất |
| --- | --- | --- |
| Bám vấn đề thực tiễn | Trích nguyên văn DA940-01; số liệu có nguồn về Bình dân học vụ số, hộ kinh doanh, lừa đảo; persona người cao tuổi; so sánh với trợ lý AI đang có trên VNeID | 1,5 trang |
| Sáng tạo, tính mới | Bảng "chatbot TTHC hiện có vs CTCV" (hỏi đáp so với dạy tự làm; kiểm chứng; sandbox; giọng nói; không chắc thì chuyển người thật) | 1 trang |
| Khả thi kỹ thuật và **kiến trúc dữ liệu** | Sơ đồ kiến trúc; schema kho tri thức TTHC (mã thủ tục, thành phần hồ sơ, phí, thời hạn, căn cứ pháp lý đến điều/khoản, hiệu lực); pipeline dữ liệu; lớp kiểm chứng; **số đo thật** trên bộ kiểm thử; chạy CPU on-prem | 3,5 trang |
| Tác động xã hội và thị trường | Kênh triển khai (VNeID, Cổng DVC, bộ phận một cửa xã, đội hình Bình dân học vụ số); chi phí mỗi xã; mô hình duy trì; KPI giảm tải một cửa (mục tiêu) | 1,5 trang |
| Năng lực và cam kết đội | Vai trò từng người; repo và commit log; kế hoạch vòng 2 theo tuần; cam kết | 1 trang |
| Trang bìa, tóm tắt | Tên, đề DA940-01, 3 con số chính, link demo và video | 1 trang |

"Dữ liệu là cốt lõi" (Điều 7) phải thấy được ngay ở trang 1. Đó là **kho tri thức TTHC chuẩn hóa có dẫn chiếu pháp
lý và hiệu lực**, cộng với **bộ kiểm thử nghiệp vụ**. Không trình bày CTCV như một ứng dụng giáo dục thuần túy.

## 3. Đề bài liên quan

### 3.1 DA940-01, chép nguyên văn

Trang: `https://dataforlife.vn/mo-hinh-ngon-ngu-lon-tieng-viet-va-tro-ly-so-cong-dan-cong-vu` (article:modified_time
09/24/2026 18:32:39). Nhãn trên trang: "DA940-01 · Trí tuệ nhân tạo · TRONG 1–2 NĂM"; "DANH MỤC BÀI TOÁN TRỌNG
ĐIỂM – VNEID NHÓM II · AI". Cơ quan (trên trang danh mục): Đề án 940 - Bộ Công An.

> **Bài toán, vấn đề cốt lõi.** Khi toàn bộ thủ tục hành chính chuyển lên trực tuyến toàn trình, hàng chục triệu
> người dân cần được hướng
>
> *(trên trang gốc, câu này bị cắt đúng như trên)*

> **Mô tả về giải pháp.** Về nghiệp vụ: trợ lý số hướng dẫn quy trình, thành phần hồ sơ, mức phí từng thủ tục; hỗ
> trợ điền biểu mẫu từ dữ liệu định danh đã có (khi công dân đồng ý); và trợ lý công vụ cho cán bộ tiếp nhận (tóm
> tắt hồ sơ, tra cứu và đối chiếu quy định). Về kỹ thuật: xây dựng theo kiến trúc truy xuất tăng cường (RAG) trên
> kho tri thức thủ tục hành chính chuẩn hóa từ Cổng Dịch vụ công quốc gia, dùng mô hình nền tiếng Việt trong nước
> tinh chỉnh cho nghiệp vụ hành chính công; có lớp dẫn chiếu căn cứ pháp lý tới điều, khoản, cảnh báo hiệu lực văn
> bản và lớp xác thực câu trả lời để kiểm soát ảo giác. Việt Nam đã có nền tảng: Viettel AI làm chủ mô hình 120 tỷ
> tham số do kỹ sư trong nước huấn luyện, thuộc nhóm hiệu suất dẫn đầu cùng quy mô; Zalo AI có họ mô hình 1-30 tỷ
> tham số và bộ tiêu chuẩn đánh giá tiếng Việt VMLU; VNG (GreenNode), VNPT AI, FPT, VinBigData đều có sản phẩm
> tương ứng.

> **Sự cần thiết đối với VNeID.** Phương thức áp dụng: tích hợp trực tiếp trong ứng dụng VNeID và cổng dịch vụ
> công, mô hình huấn luyện và suy luận hoàn toàn trên hạ tầng trong nước. Mục tiêu cụ thể: phiên bản đầu tiên phủ
> nhóm thủ tục phổ biến nhất trong 12 tháng, mở rộng toàn bộ danh mục thủ tục trong 24 tháng; đạt độ chính xác
> kiểm chứng được trên bộ kiểm thử nghiệp vụ hành chính công, hạ tỷ lệ ảo giác dưới ngưỡng cho phép và giảm tải rõ
> rệt cho bộ phận một cửa. Đây là điều kiện để dịch vụ công toàn trình thực sự đến được với người dân, không dừng ở
> việc số hóa biểu mẫu.

> **Rủi ro khi không làm chủ được công nghệ.** Nếu phụ thuộc mô hình AI thương mại nước ngoài, ba rủi ro trực diện:
> (1) dữ liệu hỏi - đáp và ngữ cảnh hồ sơ của công dân bị đưa ra hạ tầng ngoài lãnh thổ, vi phạm chủ quyền dữ liệu
> và Luật Bảo vệ dữ liệu cá nhân; (2) mô hình đóng có thể bị nhà cung cấp thay đổi hành vi, tăng giá hoặc ngừng
> phục vụ đột ngột (nhiều dịch vụ AI toàn cầu đã thay đổi chính sách truy cập và giá theo năm, có trường hợp bị hạn
> chế theo quy định kiểm soát xuất khẩu); (3) mô hình huấn luyện chủ yếu trên dữ liệu nước ngoài trả lời sai lệch
> với văn cảnh pháp lý, hành chính Việt Nam. Với hệ thống phục vụ toàn dân, cả ba rủi ro đều không thể chấp nhận.
> — Ba ô tóm tắt: "Hỏi đáp ngôn ngữ tự nhiên · Tri thức TTHC chuẩn hóa (RAG) · Suy luận trên hạ tầng trong nước".

**Yêu cầu tách ra để làm checklist**:

- Nghiệp vụ:
  - N1: hướng dẫn quy trình, thành phần hồ sơ, mức phí;
  - N2: điền biểu mẫu từ dữ liệu định danh khi công dân đồng ý;
  - N3: trợ lý công vụ cho cán bộ (tóm tắt hồ sơ, tra cứu và đối chiếu quy định).
- Kỹ thuật:
  - K1: RAG trên kho TTHC chuẩn hóa từ Cổng DVCQG;
  - K2: mô hình nền tiếng Việt trong nước, tinh chỉnh;
  - K3: dẫn chiếu pháp lý tới điều/khoản và cảnh báo hiệu lực;
  - K4: lớp xác thực chống ảo giác;
  - K5: huấn luyện và suy luận trong nước.
- KPI:
  - M1: phủ nhóm thủ tục phổ biến trong 12 tháng, toàn bộ danh mục trong 24 tháng;
  - M2: độ chính xác kiểm chứng được trên bộ kiểm thử nghiệp vụ;
  - M3: ảo giác dưới ngưỡng;
  - M4: giảm tải bộ phận một cửa.

Các đề cùng nhóm DA940 là DA940-02…18, gồm sinh trắc chống giả mạo, GPU cloud, firmware, HSM, API Gateway/WAF,
private cloud, Kubernetes, IaC, cơ sở dữ liệu, cache, message queue, Bedrock-like, SOC, quan trắc và dữ liệu lớn.
Các đề này là hạ tầng, **không phù hợp CTCV**.

### 3.2 Các đề liên quan trong Ngân hàng ý tưởng

Nguồn: `/de-bai/<id>`, đọc ngày 25/9/2026. Mọi đề BTL86 đều ghi "Mức ưu tiên / cấp thiết: Không có". Đề điểm nghẽn
cộng đồng (TTHC-, TCCN-) có mức ưu tiên riêng. Không đề nào có KPI định lượng ngoài DA940-01.

| Mã (link) | Tên đề | Đơn vị | Đầu ra mong muốn (tóm tắt sát nguyên văn "Đề xuất giải pháp") | Mức CTCV phủ |
| --- | --- | --- | --- | --- |
| DA940-01 | Mô hình ngôn ngữ lớn tiếng Việt và trợ lý số công dân, công vụ | Đề án 940 – Bộ Công an | Xem 3.1. KPI M1–M4 | Cao (thiếu N2, N3, K2) |
| BTL86-40 (`/de-bai/40`) | Trợ lý số hướng dẫn dịch vụ công cho người dân | Bộ Tư lệnh 86 – BQP | "trợ lý số dùng AI và dữ liệu thủ tục hành chính để hướng dẫn người dân theo từng tình huống cụ thể, gồm cần giấy tờ gì, nộp ở đâu, thời gian xử lý bao lâu, hồ sơ đang ở trạng thái nào". Đối tượng: người dân, doanh nghiệp nhỏ, người cao tuổi, người ít quen công nghệ, cán bộ tiếp nhận | Rất cao (trừ tra trạng thái hồ sơ thật) |
| BTL86-58 (`/de-bai/58`) | Trợ lý số đồng hành hộ kinh doanh, doanh nghiệp nhỏ về thủ tục, thuế, hóa đơn điện tử | BTL86 | "hướng dẫn từng bước về đăng ký, nghĩa vụ thuế, xuất hóa đơn điện tử, nhắc các hạn nộp… cá nhân hóa theo ngành nghề" | Trung bình (có kỹ năng kê khai thuế trong sandbox) |
| BTL86-50 (`/de-bai/50`) | Tổng đài dịch vụ công đa phương ngữ bằng trợ lý AI giọng nói | BTL86 | "voicebot hiểu và nói được nhiều phương ngữ… hướng dẫn từng bước, kiểm tra giấy tờ còn thiếu, đặt lịch hẹn, tra cứu trạng thái hồ sơ… tự động chuyển cho nhân viên khi cần". Nhấn giọng Nghệ Tĩnh, Huế, Nam Bộ; người trên 60 tuổi | Trung bình (ASR PhoWhisper, escalate; chưa có kênh gọi điện) |
| BTL86-37 (`/de-bai/37`) | Kiosk AI hỗ trợ công dân điều khiển bằng giọng nói tại xã, phường | BTL86 | Trạm hỗ trợ "AI điều khiển bằng giọng nói tiếng Việt… hướng dẫn người dân làm thủ tục mà không cần biết gõ bàn phím". Tác động: bất bình đẳng số, "dễ trở thành mục tiêu của lừa đảo" | Cao (PWA chữ to, giọng nói, chạy trên máy tính bảng ở xã) |
| BTL86-56 (`/de-bai/56`) | Trợ lý pháp lý số giải thích quyền và thủ tục bằng ngôn ngữ dễ hiểu | BTL86 | "dựa trên cơ sở dữ liệu văn bản pháp luật, giải thích… bằng ngôn ngữ đơn giản, tạo danh mục việc cần làm và mẫu đơn tham khảo… không thay thế luật sư" | Trung bình (phong cách ≤ 2 câu, trích dẫn) |
| BTL86-25 (`/de-bai/25`) | Module AI trên VNeID tóm tắt thông tư, nghị định | BTL86 | Chatbot tóm tắt văn bản, "thông tin nhanh và chính xác… không cần tìm kiếm trên các nền tảng thông tin không chính thống" | Trung bình (RAG có hiệu lực) |
| BTL86-17 (`/de-bai/17`) | Trợ lý AI nhận diện lừa đảo và chuẩn hóa trình báo tội phạm mạng | BTL86 | Hội thoại hướng dẫn kiểm tra dấu hiệu, hành động khẩn cấp; chuẩn hóa trình báo, trích thực thể (số TK, SĐT, link); "LLM tiếng Việt với kiến trúc RAG trên cơ sở tri thức được kiểm soát" | Thấp–trung bình (drill "vắc-xin" dạy nhận diện; **không** thu số TK theo bất biến 2) |
| BTL86-49 (`/de-bai/49`) | Hệ thống cảnh báo lừa đảo số trong đời sống hằng ngày | BTL86 | Kiểm tra SĐT, TK, link, mẫu tin; "AI chấm điểm rủi ro" trước giao dịch | Thấp (CTCV dạy phản xạ, không tra danh sách đen) |
| BTL86-36 (`/de-bai/36`) | Nút báo động đỏ trình báo lừa đảo trên VNeID | BTL86 | Một nút báo cáo; tự liên kết ngân hàng phong tỏa trong "giờ vàng" | Thấp (agent không có tool hành động thật, bất biến 1) |
| BTL86-15 (`/de-bai/15`) | Nhận diện lừa đảo qua cuộc gọi, tin nhắn theo thời gian thực | BTL86 | Mô hình chạy trên thiết bị nhận diện thao túng tâm lý; SDK cho VNeID/ngân hàng | Thấp |
| BTL86-45 (`/de-bai/45`) | Trợ lý số chăm sóc người cao tuổi sống một mình | BTL86 | Nhắc thuốc, lịch khám, chỉ số sức khỏe, cảnh báo, kết nối người thân | Thấp (chỉ trùng persona) |
| BTL86-51 (`/de-bai/51`) | Trợ lý ảo cho đồng bào dân tộc thiểu số tiếp cận DVC bằng tiếng mẹ đẻ | BTL86 | Đa ngôn ngữ giọng nói và văn bản, phiên dịch hai chiều với cán bộ | Thấp (lộ trình tiếng Khmer/H'Mông cho drill) |
| BTL86-31 (`/de-bai/31`) | Trợ lý ảo AI hướng dẫn hồ sơ xin giấy phép xây dựng | BTL86 | Hỏi theo tình huống, sinh danh mục hồ sơ và mẫu đơn, kiểm tra sơ bộ, "giảm mạnh tỷ lệ hồ sơ bị trả lại" | Trung bình (cùng mẫu RAG TTHC) |
| BTL86-04 (`/de-bai/4`) | Đặt lịch hẹn và theo dõi số thứ tự TTHC trên VNeID | BTL86 | Đặt lịch, danh sách giấy tờ mang theo, theo dõi hàng đợi, QR tại kiosk. Cao điểm 7h–9h | Thấp |
| TN-01 (`/de-bai/67`) | Nền tảng AI dự báo nhu cầu TTHC, tối ưu phân bổ nguồn lực cấp căn cước, định danh | Công an tỉnh Tây Ninh | Dự báo nhu cầu theo địa bàn, thời gian, loại dịch vụ; khuyến nghị nhân lực, tổ lưu động; cảnh báo quá tải | Thấp (dashboard xã chỉ là dữ liệu phụ) |
| TTHC-03 (`/de-bai/71`) | Trợ lý AI hướng dẫn thủ tục hành chính đầu-cuối (điểm nghẽn cộng đồng) | – | "nhập nhu cầu bằng ngôn ngữ tự nhiên hoặc chụp giấy tờ hiện có, AI hỏi bổ sung, lập danh mục hồ sơ, gợi ý biểu mẫu, cảnh báo thiếu sót và chỉ dẫn nơi nộp". **Mức ưu tiên: Rất cao** | Rất cao |
| TTHC-01 (`/de-bai/69`) | Kiosk tiếp nhận hồ sơ tự phục vụ cho nhóm yếu thế | – | Kiosk định danh CCCD, chọn thủ tục bằng giọng nói, tự điền mẫu từ dữ liệu dân cư. **Mức ưu tiên: Rất cao** | Trung bình |
| TTHC-09 (`/de-bai/77`) | Cổng tra cứu văn bản QPPL tích hợp AI | – | "trích dẫn điều khoản, cảnh báo hiệu lực và văn bản thay thế/sửa đổi". Mức ưu tiên: Cao | Trung bình |
| TCCN-02 (`/de-bai/89`) | Công cụ kiểm tra rủi ro trước khi chuyển tiền | – | Nhập SĐT, TK, link, QR hoặc mô tả tình huống, trả về mức rủi ro và khuyến nghị. Mức ưu tiên: Rất cao | Thấp |

### 3.3 Bối cảnh chính sách và "đối thủ" trực tiếp

- **QĐ 940/QĐ-TTg ngày 26/5/2026** phê duyệt Đề án phát triển VNeID 2026–2030, tầm nhìn 2045. Quyết định định hướng
  VNeID thành "siêu ứng dụng". Các mục tiêu AI:
  - đến 2028: "bước đầu tích hợp trí tuệ nhân tạo";
  - đến 2030: "70% tiện ích, dịch vụ được tích hợp trí tuệ nhân tạo nhằm cá nhân hóa";
  - đến 2045: "100% tiện ích, dịch vụ được tích hợp trí tuệ nhân tạo nhằm mang đến những trải nghiệm tốt nhất cho
    người dùng bao gồm các kỹ năng số khác nhau".
  - Nguồn: Báo Chính phủ. Cụm "các kỹ năng số khác nhau" là móc câu cho CTCV.
- **QĐ 826/QĐ-TTg ngày 11/5/2026** phê duyệt Chương trình Đề án 06 giai đoạn 2026–2030. Trong đó: "Tháng 9/2026, Bộ
  Công an chủ trì… triển khai trí tuệ nhân tạo AI, Trợ lý ảo để hỗ trợ dịch vụ công, thủ tục hành chính" (Dân Việt).
- **Đã có sẵn, nên phải so sánh trong hồ sơ.** C06 đã ra mắt "Cẩm nang hành chính" kèm **Trợ lý ảo AI trên VNeID**:
  - tra TTHC, hướng dẫn quy trình, hồ sơ, biểu mẫu, cảnh báo thông tin sai lệch và lừa đảo;
  - "hơn 1 tuần… trên 100.000 lượt tương tác" (ANTV, LSVN).
  - Địa phương cũng đã có chatbot TTHC, ví dụ phường Hòa Bình (Phú Thọ) và Cổng DVC TP.HCM (VietnamNet).
  - Vì vậy "hỏi đáp TTHC" **đơn thuần không còn là tính mới**.

## 4. Ánh xạ năng lực CTCV với đề và tiêu chí

Năng lực lấy từ `docs/idea.md`. Trạng thái repo theo bối cảnh E01 ngày 25/9:

- đã có: agent với 9 tool whitelist (có `search_guides`, `verify_citation`, `escalate_to_volunteer`), 1 kịch bản
  sandbox (`chuyen-khoan-qr`), 1 drill (`gia-danh-cong-an-goi-dien`);
- đã có: `data/sources.yaml` với allowlist `dichvucong.gov.vn`, thư mục `data/raw/tthc`;
- **chưa có** kho tri thức đã index;
- **chưa có** số đo eval thật.

| Yêu cầu DA940-01 | Năng lực CTCV (idea.md) | Trạng thái 25/9 | Khoảng trống cần lấp (vòng 1 viết là kế hoạch; vòng 2 làm) | Tiêu chí được điểm |
| --- | --- | --- | --- | --- |
| N1 Quy trình, thành phần hồ sơ, mức phí | Mô-đun 3 "Hỏi có căn cứ"; RAG BGE-m3 + reranker; trả lời ≤ 2 câu có trích dẫn | Tool có; kho TTHC chưa index | Crawl và chuẩn hóa N thủ tục phổ biến thành bản ghi có cấu trúc (mã, cơ quan, thành phần, phí, thời hạn, căn cứ); trả lời trường có cấu trúc, không chỉ văn bản tự do | Thực tiễn; khả thi và kiến trúc dữ liệu |
| N2 Điền biểu mẫu từ dữ liệu định danh (có đồng ý) | Sandbox mô phỏng VNeID và Cổng DVC bằng dữ liệu giả; bất biến 2 cấm lưu PII | Chưa có | Thiết kế "điền mẫu trong phiên, không lưu": ở demo dùng API định danh **giả lập** trong sandbox; khi triển khai thì lấy qua cơ chế chia sẻ có đồng ý của VNeID, bản nháp chỉ ở phía người dùng, TTL ngắn. **Cần ADR và người dùng duyệt** (chạm bất biến 2) | Thực tiễn; khả thi |
| N3 Trợ lý công vụ cho cán bộ tiếp nhận | Dashboard tình nguyện viên (mô-đun 5) | Chưa có | Chế độ "cán bộ một cửa": đối chiếu hồ sơ nộp với thành phần chuẩn của TTHC, tra quy định có trích dẫn. Nêu là lộ trình vòng 2 | Tác động (giảm tải một cửa, M4) |
| K1 RAG trên kho TTHC từ Cổng DVCQG | Pipeline `make data` (crawl theo robots, chunk, embed Qdrant), registry có sha256 | Khung có; chưa chạy thật | Không có qdrant-client hay numpy trong lock. Dùng embedding bge-m3 qua Ollama và chỉ mục đơn giản trong stdlib, hoặc xin thêm thư viện (điểm dừng) | Kiến trúc dữ liệu ("dữ liệu là cốt lõi") |
| K2 Mô hình nền tiếng Việt trong nước, tinh chỉnh | Qwen3.5-9B/2B, LoRA + DPO, GGUF | Chưa fine-tune | Rủi ro: Qwen là mô hình mở nhưng không phải của Việt Nam. Viết kiến trúc **độc lập với mô hình** (đổi base qua `config/models.yaml`); đánh giá thêm một base tiếng Việt trong nước có trọng số mở (ví dụ PhoGPT của VinAI, **chưa kiểm chứng giấy phép và chất lượng**). Đổi model là điểm dừng, cần ADR | Sáng tạo; khả thi (tự chủ) |
| K3 Dẫn chiếu điều/khoản, cảnh báo hiệu lực | Trích dẫn có ngày hiệu lực; ưu tiên văn bản mới nhất | Chưa có metadata hiệu lực | Thêm trường `can_cu_phap_ly` (văn bản, điều, khoản, ngày hiệu lực, tình trạng) vào schema kho | Kiến trúc dữ liệu; tính mới |
| K4 Lớp xác thực chống ảo giác | `verify_citation`; confidence thấp thì `escalate_to_volunteer`; "không chắc" thì escalate (bất biến 3) | Tool có, chưa có số đo | Bộ kiểm thử nghiệp vụ: câu hỏi vàng theo từng trường (thành phần, phí, thời hạn, cơ quan); đo tỷ lệ đúng, tỷ lệ ảo giác, tỷ lệ từ chối đúng | Khả thi (M2, M3); tính mới |
| K5 Huấn luyện và suy luận trong nước | Tự host vLLM hoặc llama.cpp; đường CPU với Qwen3.5-2B; không gọi API ngoài khi chạy | Đường CPU và Ollama có trên máy dev | Đo độ trễ p95 trên CPU; ghi "0 lời gọi ra nước ngoài khi chạy" có kiểm chứng (log mạng) | Khả thi; chủ quyền dữ liệu |
| (Khác biệt) Dạy người dân tự làm | Sandbox 12 kịch bản; kèm cặp qua ảnh màn hình (VLM); giọng nói; vắc-xin lừa đảo | 1 kịch bản, 1 drill | Thêm kịch bản TTHC (ví dụ nộp hồ sơ trên Cổng DVC giả lập) gắn với chính bản ghi TTHC trong kho | Sáng tạo; tác động xã hội |
| Dữ liệu vận hành cho quản lý | Dashboard lớp và bản đồ năng lực số theo thôn/tổ (ẩn danh) | Chưa có | Dữ liệu tổng hợp ẩn danh "kỹ năng nào, xã nào yếu" và câu hỏi TTHC hay gặp (không PII); nối được với TN-01 như dữ liệu đầu vào | Kiến trúc dữ liệu; tác động |

Các đề liên quan CTCV phủ thêm, chỉ nêu trong bản đề xuất, không chọn trên form:

- BTL86-40 và TTHC-03: trùng gần hoàn toàn với DA940-01 về phía công dân;
- BTL86-37 và BTL86-50: kênh giọng nói, kiosk xã;
- BTL86-58: hộ kinh doanh, thuế;
- BTL86-17 và BTL86-49: phần nhận diện lừa đảo (chỉ dạy nhận diện, không thu dữ liệu tài khoản);
- BTL86-25 và TTHC-09: tóm tắt văn bản có hiệu lực.

## 5. Khuyến nghị

### 5.1 Chọn đề trên form: DA940-01

Chọn **"Bài toán Cơ quan nhà nước" → DA940-01**. Lý do:

1. DA940 là "danh mục bài toán trọng điểm – VNeID" của chính đơn vị chủ trì (C06 vận hành VNeID). Báo chí nêu việc
   gắn với QĐ 940 là "điểm mới đáng chú ý" của mùa 4. Đây là đề BTC muốn có lời giải nhất.
2. Đề chọn từ Ngân hàng ý tưởng được cộng điểm ưu tiên. Đề tự đề xuất bị loại khỏi điểm cộng.
3. DA940-01 là đề duy nhất có KPI định lượng (M1–M4). Có KPI thì dễ chứng minh bằng số đo thật.
4. Đề yêu cầu "lớp xác thực câu trả lời để kiểm soát ảo giác" và "suy luận trong nước". Đây là hai điểm mạnh sẵn có
   của CTCV (bất biến 3, đường CPU on-prem).

Phương án B, nếu người dùng muốn tránh tầm "mô hình ngôn ngữ lớn": **BTL86-40** có nội dung gần như trùng phía công
dân và ít đội lớn cạnh tranh hơn (suy luận, chưa có dữ liệu). Đổi lại, đề này mất yếu tố "trọng điểm VNeID".
Phương án C: **TTHC-03** (điểm nghẽn cộng đồng, mức ưu tiên "Rất cao"). Không chọn nhiều đề: mỗi đội nộp một giải
pháp và form chỉ cho chọn một đề.

### 5.2 Góc tiếp cận để thắng

Câu định vị (dùng cho tên hoặc mô tả):

> CTCV: trợ lý số có kiểm chứng giúp người dân **tự làm được** thủ tục trên VNeID và Cổng Dịch vụ công, chạy hoàn
> toàn trong nước.

Sáu điểm khác biệt so với chatbot DVC thông thường, kể cả trợ lý AI đang có trên VNeID:

1. **Từ "trả lời" sang "làm được".** Người dân luyện thao tác trong sandbox mô phỏng, rồi được kèm từng bước ≤ 2
   câu, kết thúc bằng hành động có màu và chữ trên nút. Chỉ số chính là **tỷ lệ tự hoàn thành**, không phải số lượt
   chat. Điều này khớp phát biểu "nâng cao kỹ năng số cho người dân" của Trưởng BTC và việc BGK mùa 3 gợi ý
   "sandbox".
2. **Kiểm chứng thay vì tin mô hình.** Mỗi dữ kiện gắn nguồn là mã TTHC trên Cổng DVCQG cộng văn bản, điều, khoản,
   ngày hiệu lực. `verify_citation` chặn câu không có căn cứ. Khi không chắc, hệ thống **nói "không chắc" và chuyển
   người thật** (cán bộ hoặc tình nguyện viên). Báo cáo công khai các chỉ số M2 và M3 trên bộ kiểm thử nghiệp vụ.
3. **Dữ liệu là lõi.** Kho tri thức TTHC có cấu trúc, là một đồ thị nhẹ thủ tục–văn bản–điều khoản–hiệu lực, có
   pipeline cập nhật, sha256, registry giấy phép. Bộ kiểm thử nghiệp vụ được phát hành kèm. Dữ liệu vận hành ẩn danh
   cho biết xã nào vướng thủ tục nào. Điều này đáp ứng Điều 7 và góp ý "mở rộng nguồn dữ liệu" của BGK.
4. **Chủ quyền dữ liệu và chi phí gần 0.** Mô hình trọng số mở tự host, có đường CPU cho xã không có GPU, không gọi
   API nước ngoài khi chạy, không lưu CCCD/OTP/mật khẩu (bất biến 2). Cả ba rủi ro nêu trong DA940-01 đều được xử lý.
5. **Bao trùm người yếu thế.** Giọng nói là kênh mặc định, có PhoWhisper cho giọng vùng miền, chữ ≥ 20 pt, một hành
   động mỗi màn hình, dùng được ở kiosk xã (BTL86-37, BTL86-50). Có "vắc-xin lừa đảo" chống kẻ gian lợi dụng thủ tục.
6. **Hai phía công dân và cán bộ.** Có dashboard cho tình nguyện viên Bình dân học vụ số. Lộ trình vòng 2 bổ sung chế
   độ cán bộ một cửa (đối chiếu thành phần hồ sơ có trích dẫn), nhắm KPI M4 "giảm tải bộ phận một cửa".

Chiến lược bằng chứng ở vòng 1:

- 3 con số đo thật, lấy từ `make eval QUICK=1` trên CPU:
  - độ chính xác trên bộ kiểm thử TTHC;
  - tỷ lệ câu có trích dẫn hợp lệ hoặc tỷ lệ ảo giác;
  - độ trễ p95.
- Một demo chạy được, có link dùng thử hoặc ít nhất là video quay màn hình thật.
- Mọi số khác ghi là "mục tiêu vòng 2".

### 5.3 Dàn ý bản đề xuất ≤ 10 trang (BTC không có mẫu)

1. **Trang 1**:
   - tên giải pháp;
   - "Đề bài: DA940-01 – Đề án 940, Bộ Công an";
   - tóm tắt 5 dòng;
   - 3 con số đo thật;
   - link video, demo, repo;
   - bảng "đề liên quan đồng thời đáp ứng".
2. **Vấn đề thực tiễn** (1,5 trang): trích DA940-01; số liệu Bình dân học vụ số, hộ kinh doanh, lừa đảo (đều có
   nguồn); persona; khoảng trống so với trợ lý AI trên VNeID.
3. **Giải pháp và tính mới** (1 trang): 5 mô-đun; bảng so sánh 6 điểm khác biệt ở mục 5.2.
4. **Kiến trúc kỹ thuật** (1,5 trang): sơ đồ gồm planner/quarantine (CaMeL), 9 tool whitelist, RAG, lớp kiểm chứng,
   escalate; bảo mật OWASP Agentic; mô hình và đường CPU; checklist K1–K5.
5. **Kiến trúc dữ liệu** (1,5 trang): nguồn (Cổng DVCQG và các nguồn chính thống trong allowlist); schema bản ghi
   TTHC và căn cứ pháp lý; pipeline; cập nhật và cảnh báo hiệu lực; bộ kiểm thử nghiệp vụ; Luật BVDLCN 91/2025 và
   NĐ 356/2025; không PII.
6. **Kết quả thử nghiệm hiện có** (0,5–1 trang): chỉ số đo thật, kèm lệnh tái lập và commit hash; phần "chưa đạt"
   nói thẳng.
7. **Tác động và triển khai** (1,5 trang): kênh VNeID, Cổng DVC, kiosk xã, đội hình Bình dân học vụ số; chi phí
   mỗi xã; KPI M1–M4 là **mục tiêu**; mô hình duy trì (mã nguồn mở, địa phương tự host).
8. **Kế hoạch vòng 2** (0,5 trang): lịch theo tuần; rủi ro và phương án.
9. **Đội ngũ và cam kết** (1 trang): vai trò, năng lực, minh chứng repo; phần kê khai công cụ AI đã dùng khi phát
   triển (thể lệ cho phép dùng AI).

### 5.4 Video ≤ 3 phút (link YouTube không công khai hoặc Drive có quyền xem)

| Thời điểm | Nội dung |
| --- | --- |
| 0:00–0:25 | Vấn đề: người cao tuổi ở bộ phận một cửa |
| 0:25–0:50 | Một câu giải pháp và đề DA940-01 |
| 0:50–2:00 | Demo thật: hỏi bằng giọng nói về một thủ tục, câu trả lời có trích dẫn, luyện thao tác trong sandbox, một drill lừa đảo, trường hợp "không chắc" được chuyển người thật |
| 2:00–2:30 | Kiến trúc dữ liệu và 3 con số đo thật |
| 2:30–3:00 | Triển khai và đội |

Chỉ quay tính năng chạy được (Điều 7).

### 5.5 Rủi ro bị đánh giá thấp và cách giảm

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Bị xem là "một chatbot TTHC nữa" (VNeID đã có trợ lý AI, hơn 100.000 lượt tương tác) | Cao | Trang 1 nói ngay "dạy tự làm + kiểm chứng + escalate", có bảng so sánh. Chỉ số chính là tự hoàn thành và độ chính xác kiểm chứng, không đếm lượt chat |
| Không có số đo thật hoặc bị nghi làm giả số liệu (Điều 7, Điều 13) | Cao | Chỉ ghi số chạy từ `make eval` kèm commit hash. Còn lại ghi "mục tiêu". Không dùng lại con số pilot 30 người trong idea.md như kết quả |
| Chưa có kho tri thức TTHC | Cao | Tối thiểu hôm nay: một nhóm nhỏ TTHC phổ biến (ví dụ cư trú, hộ tịch, căn cước) crawl và chuẩn hóa thật, cộng bộ câu hỏi vàng tương ứng. Ghi đúng số lượng đã có |
| Mô hình nền không "trong nước" (DA940-01 viết "mô hình nền tiếng Việt trong nước") | Trung bình | Kiến trúc độc lập với mô hình; nêu tự host trọng số mở trên hạ tầng trong nước; kế hoạch vòng 2 đánh giá base tiếng Việt trong nước. Đổi model cần ADR |
| Có vẻ mâu thuẫn giữa N2 (điền mẫu từ dữ liệu định danh) và bất biến 2 (không lưu PII) | Trung bình | Thiết kế điền mẫu có đồng ý, trong phiên, không lưu; demo bằng dữ liệu giả. Coi đây là **điểm mạnh về bảo vệ dữ liệu**. Cần ADR |
| Tầm đề 1–2 năm, quy mô toàn dân; cạnh tranh với đội doanh nghiệp (Viettel/VNPT/FPT…) | Trung bình | Định vị là lớp ứng dụng kiểm chứng cộng kênh dạy kỹ năng, bổ trợ chứ không thay nền tảng lớn; lộ trình 12/24 tháng theo M1 |
| Hạn nộp mơ hồ, nộp sát giờ | Trung bình | Nộp trong ngày 25/9, sớm nhất có thể. Kiểm tra `/preview`. Video để chế độ ai có link cũng xem được |
| Thiếu thành viên (trang chủ ghi 03–10) | Trung bình | Đăng ký ≥ 3 người. Mỗi người điền đủ trường bắt buộc và gõ chữ ký cam kết |
| Nội dung lừa đảo bị hiểu là dạy lừa | Thấp | Drill chỉ ở mức mẫu hành vi, gắn nhãn mô phỏng (đã là luật của repo) |
| Bản quyền dữ liệu crawl | Thấp | Chỉ dùng để truy xuất và trích dẫn, không phân phối lại. Kiểm tra robots và ToS (`data/sources.yaml` có `tos_checked_on`) |

### 5.6 Checklist nộp ngày 25/9/2026

- [ ] Tạo hồ sơ tại `/tham-gia-cuoc-thi` → "Bắt đầu đăng ký"; lưu lại email và mật khẩu.
- [ ] Nhập đội ≥ 3 thành viên, đủ trường bắt buộc; đội trưởng ≥ 18 tuổi, có link GitHub hoặc portfolio.
- [ ] Chọn đề: Bài toán Cơ quan nhà nước → nhóm AI → **DA940-01**.
- [ ] Tên giải pháp ≤ 400 ký tự; mô tả ngắn ≤ 2.000 ký tự (vấn đề, giải pháp, giá trị).
- [ ] Bản đề xuất **PDF** ≤ 10 trang, ≤ 10 MB.
- [ ] Link video ≤ 3 phút, mở được khi chưa đăng nhập.
- [ ] Link demo (nếu có) chỉ trỏ tới phần chạy thật.
- [ ] Mọi thành viên gõ chữ ký cam kết → xem `/preview` → "Gửi hồ sơ dự thi".
- [ ] Không công bố kết quả vòng trước BTC; giữ bản sao mọi tệp đã nộp.

## 6. Nguồn đã đọc (truy cập 25/9/2026)

Trang chính thức dataforlife.vn (HTML gốc tải bằng curl):

- https://dataforlife.vn/mo-hinh-ngon-ngu-lon-tieng-viet-va-tro-ly-so-cong-dan-cong-vu (DA940-01)
- https://dataforlife.vn/the-le (Thể lệ mùa 4, Điều 1–14)
- https://dataforlife.vn/ (trang chủ: lộ trình, giải thưởng, 03–10 thành viên)
- https://dataforlife.vn/gioi-thieu (nội dung vẫn là mùa 3 "Hack for Growth 2025")
- https://dataforlife.vn/ngan-hang-y-tuong ; https://dataforlife.vn/bai-toan-nha-nuoc ; https://dataforlife.vn/diem-nghen-cong-dong
- https://dataforlife.vn/tham-gia-cuoc-thi ; /overview ; /team-members ; /pick-idea ; /submission ; /js/Dashboard.js
- https://dataforlife.vn/tin-tuc ; /don-vi-dong-hanh ; /lien-he (404)
- Đề: /de-bai/40, /58, /50, /56, /49, /17, /36, /45, /51, /67, /4, /25, /37, /31, /15, /14, /53, /52, /55, /71, /69, /89, /77
- Tin mùa 3 trên dataforlife.vn: /chung-ket-cuoc-thi-data-for-life-hack-for-growth-mua-3-nam-2025 ;
  /vinh-danh-cac-doi-thi-xuat-sac-data-for-life-mua-3 ;
  /chuc-mung-30-doi-thi-xuat-sac-duoc-lua-chon-vao-vong-trien-lam-cuoc-thi-data-for-life-mua-3-hack-for-growth-2025 ;
  /cong-bo-danh-sach-60-doi-thi-vuot-qua-vong-ho-so-cuoc-thi-data-for-life-2025 ;
  /sprinting-with-mentors-but-toc-cung-tri-thuc-lan-toa-cung-doi-moi-sang-tao ;
  /hoi-thao-khoi-dong-cuoc-thi-tim-kiem-giai-phap-cong-nghe-data-for-life-mua-3

Báo chí và cơ quan nhà nước:

- VTC News, phát động 28/8/2026: https://vtcnews.vn/data-for-life-2026-tim-kiem-giai-phap-du-lieu-tu-nhung-bai-toan-thuc-te-ar1037147.html
- VJST, BTC và kế hoạch 398: https://vjst.vn/bo-cong-an-cong-bo-cuoc-thi-data-for-life-2026-voi-chu-de-build-together-102959.html
- Đại biểu Nhân dân, điểm mới QĐ 940, Cổng Sáng kiến quốc gia, lab: https://daibieunhandan.vn/ra-mat-cong-sang-kien-khoa-hoc-va-cong-nghe-phat-dong-cuoc-thi-data-for-life-mua-4-10429009.html
- VTV, hơn 5.000 ý tưởng: https://vtv.vn/hon-5000-y-tuong-duoc-gui-toi-data-for-life-mua-4-100260828141316615.htm
- VTV, phát động tại Singapore: https://vtv.vn/phat-dong-cuoc-thi-data-for-life-mua-4-tai-singapore-mo-rong-ket-noi-doi-moi-sang-tao-quoc-te-100260912170719233.htm
- Nhân Dân: https://nhandan.vn/phat-dong-cuoc-thi-data-for-life-mua-4-nam-2026-post988654.html ; https://nhandan.vn/cuoc-thi-data-for-life-mua-4-ket-noi-doi-moi-sang-tao-trong-asean-post988120.html
- VTC News, Singapore: https://vtcnews.vn/data-for-life-2026-mo-rong-ket-noi-quoc-te-tai-singapore-ar1039415.html
- TTXVN Chính sách cuộc sống: https://chinhsachcuocsong.vnanet.vn/bo-cong-an-phat-dong-cuoc-thi-data-for-life-2026-va-cong-bo-cong-sang-kien-khoa-hoc-va-cong-nghe/94858.html
- Báo Tin tức: https://baotintuc.vn/phat-dong-cuoc-thi-data-for-life-2026-va-cong-bo-cong-sang-kien-khoa-hoc-va-cong-nghe-post1269512.html
- Công an Sơn La (lịch 10/8–15/9): https://congan.sonla.gov.vn/bo-cong-an-phat-dong-cuoc-thi-data-for-life-mua-4-nam-2026/
- Công an Cần Thơ: https://congan.cantho.gov.vn/hoat-dong-cua-cong-an-thanh-pho/cong-an-thanh-pho-can-tho-tuyen-truyen-huong-ung-cuoc-thi-quoc-te-data-for-life-mua-4-nam-2026-9675.html ; https://congan.cantho.gov.vn/hoat-dong-cua-lanh-dao-bo/cong-bo-cong-sang-kien-khoa-hoc-va-cong-nghe-phat-dong-cuoc-thi-data-for-life-2026-10300.html
- CAND, chung kết mùa 3: https://cand.com.vn/Khoa-hoc-Quan-su/chung-ket-cuoc-thi-data-for-life--hack-for-growth-mua-3-nam-2025-i791067
- CAND, "Sức hấp dẫn của một cuộc thi" (Cheppy, quy mô các mùa): https://cand.com.vn/Hoat-dong-LL-CAND/suc-hap-dan-cua-mot-cuoc-thi-i796687
- CAND, 30 đội mùa 3: https://cand.com.vn/Khoa-hoc-Quan-su/chon-30-doi-xuat-sac-vao-vong-trien-lam-cuoc-thi-data-for-life-2025-i790349
- CAND, "Ươm mầm giải pháp" (Ban Cố vấn ĐHBK): https://cand.com.vn/Khoa-hoc-Quan-su/data-for-life-2025-uom-mam-giai-phap-lan-toa-gia-tri-so-i781453
- CafeF, tọa đàm BGK TECHFEST 2025: https://cafef.vn/san-pham-cong-nghe-du-lieu-duoc-mo-duong-de-di-vao-doi-song-188251215135119745.chn
- NLĐ, LandBase: https://thitruong.nld.com.vn/data-for-life-2025-hack-for-growth-landbase-doat-giai-voi-giai-phap-ai-du-lieu-bat-dong-san-196251224144144559.htm
- Đại biểu Nhân dân, GoTrust mùa 2: https://daibieunhandan.vn/doi-gotrust-dat-giai-nhat-cuoc-thi-data-for-life-post397726.html
- Tuổi Trẻ/PLO, chung kết 2024: https://tuoitre.vn/plo/chung-ket-cuoc-thi-quoc-te-data-for-life-2024-goi-ten-doi-chien-thang-109822163.htm
- C06, lan tỏa giải pháp mùa 3: https://canhsatquanlyhanhchinh.gov.vn/gioi-thieu/lan-toa-giai-phap-tu-cuoc-thi-data-for-life-chu-de-hack-for-growth-2025-gop-phan-ghi-dau-trong-trien-lam-cong-nghe-3912
- Báo Chính phủ, QĐ 940/QĐ-TTg: https://baochinhphu.vn/phat-trien-vneid-thanh-sieu-ung-dung-dong-vai-tro-trung-tam-trong-he-sinh-thai-so-quoc-gia-102260527174751974.htm
- Dân Việt, QĐ 826/QĐ-TTg, AI và trợ lý ảo tháng 9/2026: https://etime.danviet.vn/da-ro-lo-trinh-chinh-phu-cho-phep-tro-ly-ao-ai-tu-van-dich-vu-cong-thu-tuc-hanh-chinh-d1425851.html
- ANTV, Cẩm nang hành chính và trợ lý AI VNeID: https://antv.gov.vn/xa-hoi-4/cam-nang-hanh-chinh-ket-hop-tro-ly-ao-ai-tren-ung-dung-vneid-BFC14C644.html
- LSVN, hướng dẫn trợ lý AI của Bộ Công an: https://lsvn.vn/huong-dan-su-dung-tro-ly-ao-ai-cua-bo-cong-an-tra-cuu-thu-tuc-hanh-chinh-a160646.html
- Công an Thanh Hóa, trợ lý AI trên VNeID: https://conganthanhhoa.gov.vn/de-an-06/huong-dan-su-dung-tro-ly-ao-ai-ho-tro-hanh-chinh-cong-tren-vneid.html
- VietnamNet, chatbot TTHC phường Hòa Bình: https://vietnamnet.vn/chatbot-ai-giup-tra-cuu-dich-vu-cong-thu-hep-khoang-cach-thong-tin-2524097.html

Không truy cập được hoặc không tìm thấy:

- Link PDF thể lệ (`#`);
- trang `/lien-he` (404);
- API danh sách đề (401, cần đăng nhập);
- mẫu bản đề xuất chính thức;
- trang Q&A;
- thông báo gia hạn chính thức;
- trọng số chấm điểm.

## Đính chính (25/9/2026)

- §5.2 "3 con số đo thật, lấy từ `make eval QUICK=1` trên CPU": lượt đo thật dùng
  `uv run python -m ctcv_eval.harness --suite qa` (đầy đủ, vì tập quick không có câu cần từ chối) trên laptop có GPU
  rời NVIDIA RTX 4050; Ollama nạp cả hai mô hình lên GPU và `qwen3.5:2b` là lượng tử Q8_0 (`eval/reports/env-tthc.json`).
  Hồ sơ không được ghi "CPU, không GPU" cho các số này; chưa có số đo chỉ-CPU.
