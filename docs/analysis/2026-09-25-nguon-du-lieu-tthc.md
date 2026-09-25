# Khảo sát khả thi nguồn dữ liệu cho kho tri thức thủ tục hành chính (TTHC)

Ngày 25/9/2026 · phục vụ đề DA940-01 (Data for Life 2026) và E03 · người thực hiện: Claude Code (agent dữ liệu).
Phạm vi: khảo sát và lấy mẫu có giới hạn, **chưa crawl hàng loạt**. Mọi yêu cầu HTTP dùng User-Agent
`CTCV-crawler/0.1 (Binh dan hoc vu so; muc dich hoc tap; 1 req/s)`, cách nhau ≥ 1,2 giây, đã đọc robots.txt trước.
Mẫu thô nằm ở `data/raw/tthc/_samples/` (đã gitignore theo `data/raw/*`, không commit, không phân phối lại).

## 1. Kết luận

**Phương án khả thi nhất hôm nay: Cổng Dịch vụ công Bộ Công an** (`dichvucong.bocongan.gov.vn`, tên miền con của
`bocongan.gov.vn` — đã có trong allowlist `data/sources.yaml`, trạng thái `da_xac_nhan`).

- Trang render phía máy chủ (HTML đầy đủ, không cần chạy JS); robots.txt chỉ chặn `/tttl/` với Googlebot/AdsBot,
  không có luật cho `*` → được phép với crawler của dự án.
- Chân trang ghi: *"Khi sử dụng lại thông tin, đề nghị ghi rõ nguồn 'Cổng Dịch vụ công - Bộ Công an'"* → dùng
  được cho truy xuất + trích dẫn có ghi nguồn (vẫn giữ `redistribute: false` cho bản chụp thô).
- Đã mở **109/109 trang chi tiết** ở 9 lĩnh vực, 0 lỗi; **14/14 mục** có mặt ở mọi trang (mã, lĩnh vực, cơ quan,
  mức độ DVC, cách thức, trình tự, thời hạn, phí, lệ phí, thành phần hồ sơ, yêu cầu điều kiện, căn cứ pháp lý,
  biểu mẫu, kết quả). 51/109 trang có link tải biểu mẫu (.doc/.pdf).
- Giới hạn: chỉ bao phủ TTHC thuộc Bộ Công an (cư trú, căn cước, lý lịch tư pháp, GPLX, đăng ký xe, hộ chiếu/xuất
  nhập cảnh, xử phạt giao thông). Hộ tịch, hộ kinh doanh, thuế, BHXH/BHYT, an sinh, đất đai, xây dựng **chưa có
  nguồn lấy được hợp lệ** (xem §2, §6).

**Cổng DVC quốc gia (`dichvucong.gov.vn`) hiện không lấy được một cách hợp lệ bằng máy:** cổng mới (do Trung tâm
dữ liệu quốc gia — Bộ Công an vận hành) là SPA React; mọi đường dẫn (kể cả URL cũ
`/p/home/dvc-tthc-thu-tuc-hanh-chinh-chi-tiet.html?ma_thu_tuc=...`) trả cùng một vỏ HTML 5.222 byte `<div id="root">`;
nội dung chỉ có sau khi chạy `/assets/index-*.js`, mà robots.txt **`Disallow: /assets/` cho `User-agent: *`** (chỉ
cho Googlebot tải JS/CSS). Render bằng Playwright đồng nghĩa tải đường dẫn bị cấm → **không làm**.

## 2. Robots.txt và điều khoản (kiểm 25/9/2026, 01:3x giờ VN)

| Tên miền | Trong allowlist? | robots.txt | Kết luận |
| --- | --- | --- | --- |
| dichvucong.gov.vn | có (`da_xac_nhan`) | 200; `Allow: /`; cấm `/ho-so-cong-dan/`, `/nop-ho-so`, `/tao-ho-so`, `/sua-ho-so/`, `/sso`, `/dang-nhap`, **`/assets/`**; sitemap 61 URL | Chỉ lấy được vỏ SPA; render cần `/assets/` (bị cấm). Trang `/dieu-khoan-su-dung` cũng là SPA → **chưa đọc được ToS**. |
| thutuc.dichvucong.gov.vn | có (tên miền con) | **503** (openresty) ×2 lần, cả trang gốc | RFC 9309: robots 5xx ⇒ coi như cấm toàn bộ. Không thử lại bằng UA trình duyệt (né chặn). |
| csdl.dichvucong.gov.vn | có (tên miền con) | **503** ×2 lần | Như trên. |
| dichvucong.bocongan.gov.vn | có (tên miền con bocongan.gov.vn) | 200; chỉ `User-agent: Googlebot/AdsBot → Disallow: /tttl/` | **Được phép**; SSR; chân trang cho phép dùng lại có ghi nguồn. |
| vbpl.vn | có (`can_xac_nhan`, chỉ tra cứu) | 200; cấm `/api/`, `/Pages/` | Next.js; dữ liệu tải qua `/api/` (bị cấm) → giữ quy ước: người tra tay, ghi `docs/legal/refs.yaml`. |
| vanban.chinhphu.vn | **không** | 200; `Allow: /` | Chỉ đọc robots; muốn dùng phải thêm vào allowlist (người dùng duyệt). |
| thuvienphapluat.vn | **không** | 200; `Allow: /` + sitemap | Chỉ đọc robots. Là trang thương mại (nội dung có bản quyền, nhiều phần cần tài khoản) → **không dùng** làm nguồn. |

Mẫu robots lưu ở `data/raw/tthc/_samples/robots/`.

## 3. Mẫu đã lấy (5 trang tiêu biểu trong 109)

| matt (cổng BCA) | Mã TTHC | Tên | Ghi chú |
| --- | --- | --- | --- |
| 26360 | 1.004222 | Đăng ký thường trú | Phí 20.000 đ trực tiếp / 10.000 đ trực tuyến; 7 ngày làm việc; mẫu CT01 (.doc) |
| 26052 | 2.000200 | Cấp thẻ căn cước cho người từ đủ 14 tuổi (Công an tỉnh) | 2 link biểu mẫu |
| 61555 | 3.000333 | Cấp phiếu lý lịch tư pháp cho công dân (Công an tỉnh) | Phí dẫn TT 16/2025/TT-BTC; 10–15 ngày |
| 29497 | 1.001456 | Cấp hộ chiếu phổ thông ở trong nước (cấp tỉnh) | |
| 61616 | 3.000346 | Cấp giấy phép lái xe | |

Lưu ý: mã `1.001612` (ví dụ trong nhiệm vụ) **không phải** "đăng ký thường trú"; mã thật là `1.004222`.
Nhiều khả năng `1.001612` là "đăng ký thành lập hộ kinh doanh" — chưa mở được trang để xác minh (`verified: false`).

## 4. Trường lấy được và chất lượng

- Lấy trực tiếp: `ten` (h4 `.tthc-title`), 14 mục trong accordion `.tthc-list-item` (nhãn → nội dung), link biểu mẫu
  `/public_dir/tttl/...`. Không có: **ngày cập nhật/ngày công bố**, cấp thực hiện dạng mã (phải suy từ tên/cơ quan),
  số quyết định công bố TTHC.
- Chất lượng cần xử lý: mục "Phí" gộp kênh + thời hạn + số tiền trong ô bảng ("Trực tiếp 07 Ngày làm việc20.000...")
  → phải parse theo ô `<td>`, không theo text phẳng; "Thành phần hồ sơ" là bảng (tên giấy tờ, bản chính, bản sao);
  "Căn cứ pháp lý" có thể **cũ** (vd. LLTP chỉ dẫn Luật 28/2009/QH12) → không tự khẳng định hiệu lực.
- **HTML thô không ổn định**: tải lại cùng trang cho sha256 khác (CSRF token, nonce SSO, `?v=` của CSS). → Hash để
  phát hiện thay đổi phải tính trên **nội dung đã chuẩn hóa** (14 mục, NFC, gộp khoảng trắng), không trên HTML thô.
- Một mã không theo định dạng quốc gia: nộp phạt giao thông `C08_XPHCDB` (mã nội bộ cổng).

## 5. Tốc độ và dung lượng (đo thật)

109 trang chi tiết trong 159 giây (≈ 1,46 s/trang ở nhịp 1,2 s); HTML trung vị 80 KB; văn bản 14 mục trung vị
≈ 4.700 ký tự. Toàn bộ 9 danh sách + 109 trang: 11 MB. Ước tính 500 TTHC ≈ 12–13 phút, kèm biểu mẫu ≈ 25 phút.

## 6. Đề xuất bản ghi chuẩn hóa (JSON) — `data/clean/tthc/<ma_thu_tuc>.json`

```json
{
  "ma_thu_tuc": "1.004222",
  "ten": "Đăng ký thường trú",
  "linh_vuc": "Đăng ký, quản lý cư trú",
  "co_quan_thuc_hien": ["Công an cấp xã"],
  "cap_thuc_hien": "xa",                      // bo | tinh | xa (suy từ cơ quan/tên, cờ inferred=true)
  "doi_tuong": ["cong_dan"],
  "muc_do_dvc": "mot_phan",                   // thong_tin | mot_phan | toan_trinh
  "cach_thuc": [{"kenh": "truc_tiep", "thoi_han": "07 ngày làm việc", "phi_vnd": 20000, "ghi_chu": "..."},
                {"kenh": "truc_tuyen", "thoi_han": "07 ngày làm việc", "phi_vnd": 10000}],
  "trinh_tu": ["Bước 1: ...", "Bước 2: ..."],
  "thanh_phan_ho_so": [{"truong_hop": "Chỗ ở thuộc sở hữu của mình", "giay_to": "...", "ban_chinh": 0, "ban_sao": 1, "mau": "CT01"}],
  "le_phi": "Không",
  "yeu_cau_dieu_kien": "không",
  "can_cu_phap_ly": [{"so_hieu": "68/2020/QH14", "ten": "Luật Cư trú", "refs_id": null}],
  "bieu_mau": [{"ten": "Tờ khai thay đổi thông tin cư trú (CT01)", "url": "https://.../CT01.doc"}],
  "ket_qua": ["Cập nhật thông tin trong CSDL quốc gia về dân cư"],
  "meta": {
    "source_url": "https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26360",
    "source_portal": "Cổng Dịch vụ công - Bộ Công an", "agency": "Bộ Công an",
    "fetched_at": "2026-09-24T18:38:59Z", "sha256_raw": "...", "sha256_content": "...",
    "updated_at": null, "effective_date": null,          // nguồn không công bố → null, KHÔNG tự điền
    "license_note": "Ghi rõ nguồn khi sử dụng lại; không phân phối lại bản chụp",
    "parser_version": "tthc-bca/1", "lang": "vi", "nfc": true
  }
}
```

**Chunk theo mục** (mỗi chunk mang toàn bộ `meta` + `ma_thu_tuc`, `ten`, `section`, `anchor`):
`tong_quan` (tên, lĩnh vực, cơ quan, cấp, mức độ DVC, đối tượng, kết quả) · `trinh_tu` (tách theo bước nếu > 1.200 ký
tự) · `thanh_phan_ho_so` (tách theo "trường hợp") · `phi_le_phi` · `thoi_han` (gộp với cách thức) · `dieu_kien` ·
`can_cu_phap_ly` · `bieu_mau`. Tiền tố chunk: "Thủ tục <tên> (mã <mã>) — <mục>:" để BM25 bắt mã/tên.
Metadata bắt buộc để `verify_citation` dùng: `source_url`, `ma_thu_tuc`, `co_quan`, `cap_thuc_hien`, `fetched_at`,
`sha256_content`, `updated_at|effective_date` (null được, nhưng khi null câu trả lời phải nói "theo cổng BCA, truy
cập ngày <fetched_at>").

## 7. Dự phòng khi bị chặn / thiếu nguồn (không vượt robots, không né chặn)

1. **Xin quyền dữ liệu từ đơn vị ra đề** (Trung tâm dữ liệu quốc gia — Bộ Công an vận hành cả `dichvucong.gov.vn` và
   CSDL TTHC): văn bản xin API/xuất dữ liệu CSDL TTHC hoặc xác nhận cho phép render SPA; nêu trong bản đề xuất như
   hạng mục "dữ liệu cần BTC cung cấp". Đây là đường chính cho các lĩnh vực ngoài Bộ Công an.
2. Theo dõi `thutuc.`/`csdl.dichvucong.gov.vn`: kiểm lại robots.txt 1 lần/ngày; khi trả 200 và cho phép → lấy theo mã.
3. Nguồn công khai thay thế cần người dùng duyệt thêm vào allowlist: cổng DVC cấp tỉnh (nhiều tỉnh dùng chung
   CSDL TTHC, SSR), cổng/chuyên trang TTHC của bộ ngành (Bộ Tư pháp — hộ tịch; BHXH Việt Nam; Cục Thuế — `gdt.gov.vn`
   đã có allowlist), Quyết định công bố TTHC trên `vanban.chinhphu.vn`/`congbao.chinhphu.vn` (phụ lục chứa đủ nội
   dung TTHC; cần `pypdf` — đã có trong allowed-deps nhưng chưa trong uv.lock).
4. Không dùng: Playwright trên `dichvucong.gov.vn` (cấm `/assets/`), đổi User-Agent giả trình duyệt, thuvienphapluat.vn.

## 8. Rủi ro

- **Độ phủ**: nguồn hợp lệ hiện chỉ có TTHC Bộ Công an (~50 thủ tục người dân hay dùng) — thiếu hộ tịch, hộ kinh
  doanh, BHXH, đất đai, xây dựng (41 mục trong danh sách đề xuất còn `verified: false`, 30 mục chưa có mã).
- **Mã/nội dung lỗi thời**: sau sắp xếp chính quyền 2 cấp (1/7/2025) nhiều TTHC được công bố lại (mã `1.01xxxx`,
  `3.000xxx`); căn cứ pháp lý trên trang có thể chưa cập nhật; trang không có ngày cập nhật → phải hiện ngày truy cập.
- **Giấy phép**: ToS `dichvucong.gov.vn` chưa đọc được; cổng BCA chỉ có câu "ghi rõ nguồn" ở chân trang — cần một
  thành viên người xác nhận và ghi `tos_checked_on` trước khi đưa vào `sources.yaml`/registry (`redistribute: false`).
- **Hash nhiễu**: dùng `sha256_content` thay vì hash HTML thô, nếu không cảnh báo "hash đổi" sẽ bật mọi lần crawl.

## 9. Việc tiếp theo đề xuất (E03, cần người dùng duyệt)

1. Duyệt `data/sources.tthc.candidates.yaml` (50 verified + 41 chưa xác minh = 91); chuyển mục đã duyệt vào `sources.yaml`.
2. Hiện thực `crawl` cho mẫu URL `dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=` + parser `tthc-bca/1` (lxml
   có sẵn trong uv.lock) + test fixture từ 3 trang mẫu (đã cắt PII — trang không có PII).
3. Gửi đề nghị dữ liệu CSDL TTHC cho BTC (mục §7.1).
