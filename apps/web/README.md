# @ctcv/web — PWA "Cầm Tay Chỉ Việc"

Giao diện cho người dân (ưu tiên 50+ tuổi): **chữ ≥ 20 pt, một hành động chính mỗi màn hình, nút to có hình + chữ, giọng nói là kênh mặc định**, luôn có "Nói lại" và "Gọi tình nguyện viên", nhãn "Ứng dụng mô phỏng" trên mọi màn hình (idea §4, prompt §5 D3).

Khung E01 có màn hình chính: tiêu đề, nhãn mô phỏng, vùng phụ đề chữ to, nút micro "Nói với tôi", nút "Nói lại" và chân trang luôn hiện "Gọi tình nguyện viên". Sandbox 12 kịch bản đến ở E02, nói–nghe thật ở E04, kèm cặp qua ảnh ở E08, chạy không mạng ở E12.

## Hỏi thủ tục và kiểm tra hồ sơ (DFL 2026, ADR-007 C7)

Ba màn hình, điều hướng bằng dấu `#` (không cần thư viện điều hướng):

| Địa chỉ                | Cho ai              | Làm gì                                                                                                                                                                                                          |
| ---------------------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/` (mọi dấu `#` khác) | Người dân           | Màn hình E01 + nút "Hỏi thủ tục" (`hoi-thu-tuc-button`) nằm dưới 3 nút cũ, không đẩy chúng xuống                                                                                                                |
| `#hoi-thu-tuc`         | Người dân (có lớp)  | Ô hỏi, 3 câu mẫu, nút xanh "Hỏi"; câu trả lời chữ to, nút xanh "Nguồn" mở bảng nguồn (tên trang, cổng/cơ quan, "Lấy ngày dd/mm/yyyy" theo giờ Việt Nam, đoạn trích, liên kết https), thẻ "Giấy tờ cần chuẩn bị" |
| `#can-bo`              | Cán bộ một cửa, TNV | Đăng nhập → tìm thủ tục → chọn trường hợp → đánh dấu giấy tờ đã nhận → "Kiểm tra hồ sơ" → danh sách thiếu (đỏ), tin nhắn gửi người dân, nút "Sao chép tin nhắn", liên kết nguồn                                 |

- **Vào lớp**: mở đường dẫn trong mã QR của lớp `/?lop=<mã>#hoi-thu-tuc` → gọi `POST /v1/auth/join` đúng một lần (tên hiển thị "Học viên"), rồi xóa `lop` khỏi thanh địa chỉ. Chưa có mã thì màn hỏi chỉ mời "Bác quét mã QR của lớp để bắt đầu nhé."
- **Mã đăng nhập chỉ nằm trong bộ nhớ** (`src/state/session.ts`, không localStorage/sessionStorage/cookie); tải lại trang là quên. `src/api/client.ts` tự gắn `Authorization: Bearer`. Mật khẩu cán bộ đọc từ ô nhập một lần, gửi đi rồi xóa, không giữ trong state.
- **Câu hỏi**: gộp mọi xuống dòng và khoảng trắng thừa thành một dấu cách trước khi gửi (API coi văn bản nhiều dòng là nội dung dán và từ chối); Enter là gửi, Shift+Enter xuống dòng; tối đa 500 ký tự; chờ tối đa `ASK_TIMEOUT_MS` = 150 giây (API chờ mô hình tới `serving.timeout_s` = 120 giây trong `config/rag.yaml`). Câu hỏi không được lưu ở trình duyệt.
- **Trung thực**: hộp vàng "Câu này cháu chưa chắc…" khi `escalate`, **không** có nút hay chữ "đã báo tình nguyện viên" (chưa có hàng đợi thật); nút "Gọi tình nguyện viên" chỉ hướng dẫn nhờ tình nguyện viên của lớp hoặc cán bộ một cửa. Nhãn "Nội dung do AI tạo" trên mọi câu trả lời.
- **Cuộn**: câu trả lời mới và kết quả kiểm tra tự cuộn lên đầu và nhận tiêu điểm (chỉ đặt tiêu điểm thì không cuộn khi tiêu đề nằm sau chân trang).
- **Chân trang "Gọi tình nguyện viên"** dùng `position: sticky` (không phải `fixed` + khoảng đệm đoán trước): luôn ở đáy màn hình khi cuộn nhưng giữ chỗ riêng ở cuối trang, nên dù nút xuống hai dòng, có lời nhắc phía trên hay chữ hệ thống phóng to, phần cuối trang không bao giờ bị che (e2e `expectEndClearOfFooter` trên 3 viewport, kèm kiểm không cuộn ngang).
- **Tên giấy tờ dài** (dữ liệu thật tới 600 ký tự, nhãn trường hợp tới 900): `src/components/ExpandableText.tsx` hiện câu đầu (nếu câu đầu ≥ `textPreview.minSentenceChars` = 24 và ≤ `textPreview.maxChars` = 120 ký tự) hoặc tối đa 120 ký tự cắt ở ranh giới từ, thêm "…", kèm nút "Xem đủ"/"Thu gọn" (≥ 56 px, `aria-expanded`, `aria-controls`). Bản rút gọn luôn là phần đầu của nguyên văn; số bản chính/bản sao/mẫu luôn hiện. Nút nằm ngoài nhãn ô đánh dấu nên bấm "Xem đủ" không đánh dấu giấy tờ. Áp dụng cho thẻ "Giấy tờ cần chuẩn bị", danh mục và danh sách thiếu ở màn cán bộ, tiêu đề nhóm trường hợp; ô chọn trường hợp hiện bản rút gọn (hai nhãn trùng phần đầu thì giữ nguyên văn), giá trị gửi API vẫn là nguyên văn.
- **Giấy tờ chỉ cần khi đúng trường hợp**: giấy có cờ `conditional: true` hoặc trạng thái `neu_ap_dung` (trường tùy chọn của hợp đồng C6, API cũ không gửi thì hiển thị như trước) có nhãn vàng "Chỉ cần nếu đúng trường hợp" ngay trong nhãn ô đánh dấu; ở kết quả kiểm tra, giấy này **không** nằm trong "Còn thiếu N giấy tờ" (N đếm đúng danh sách đỏ) mà ở mục riêng "Chỉ cần nếu đúng trường hợp, anh/chị hỏi thêm người dân:".
- **Trường hợp của hồ sơ** (`#can-bo`): khi chưa gửi `case_label`, API chỉ trả giấy tờ chung và `needs_case: true`. Nếu mọi giấy tờ đều thuộc một trường hợp (vd "Đăng ký tạm trú" 1.004194), danh mục trống và màn hình nhắc chọn trường hợp. Chọn trường hợp thì gọi lại `POST /v1/coach/intake-check` với `procedure_id` + `case_label`, `received: []`. Danh mục được làm mới; dấu đã đánh được nhớ theo từng giấy tờ; lỗi thì giữ lựa chọn cũ; chỉ câu trả lời mới nhất được dùng. Thủ tục không có trường hợp thì không hiện ô chọn và không gọi thêm.
- **Nhãn trường hợp** là nguyên câu dẫn của nguồn ("Hồ sơ đăng ký tạm trú gồm"). `displayCaseLabel` (`src/screens/DocumentsCard.tsx`) chỉ bỏ đuôi "gồm"/"bao gồm"/", hồ sơ gồm"/":" khi hiển thị; giá trị gửi API vẫn giữ nguyên câu gốc.
- Màn cán bộ là công cụ cho nhân viên nên không có "Nói lại"/"Gọi tình nguyện viên"; vẫn chữ ≥ 20 pt, vùng bấm ≥ 56 px, tương phản ≥ 7:1.

## Yêu cầu

Node ≥ 20, pnpm ≥ 10 (bản pnpm được `packageManager` ở gốc kho mã chọn tự động). Cài từ gốc kho mã: `pnpm install` (hoặc `make install`).

## Lệnh

Chạy trong `apps/web` (`pnpm -C apps/web <lệnh>` từ gốc):

| Lệnh                          | Làm gì                                                                                                                                                                       |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm dev`                    | Vite dev server ở cổng `ports.web` của `config/app.yaml` (5173); `/v1` được chuyển tiếp sang cổng `ports.api`                                                                |
| `pnpm build` / `pnpm preview` | Đóng gói PWA (manifest + service worker) vào `dist/` và xem thử                                                                                                              |
| `pnpm lint` / `pnpm format`   | ESLint 9 (typescript-eslint, react-hooks, jsx-a11y, cấm `style=` inline) + Prettier                                                                                          |
| `pnpm typecheck`              | `tsc --noEmit` cho mã ứng dụng và cho file cấu hình                                                                                                                          |
| `pnpm test`                   | Vitest + Testing Library (jsdom). **Không** chạy e2e                                                                                                                         |
| `pnpm e2e`                    | Playwright trên 3 viewport của `config/app.yaml` (360×800, 390×844, 412×915) + axe; cần Chromium (`pnpm exec playwright install chromium`, tự động khi `make install E2E=1`) |
| `pnpm a11y`                   | Chỉ ca kiểm tra axe (dùng bởi `make release-check`)                                                                                                                          |

`make lint`, `make e2e` (khi `E2E=1`) và `make audit` ở gốc gọi lại các lệnh này.

## Cấu trúc

```
apps/web/
  index.html                lang="vi", viewport, cỡ chữ cơ sở
  ctcv-config.ts            đọc config/app.yaml cho vite/playwright/test (ngưỡng, cổng, viewport)
  vite.config.ts            React + vite-plugin-pwa (manifest tiếng Việt) + cấu hình vitest
  tailwind.config.ts        Tailwind 3 lấy token từ src/theme/tokens.ts (không có cỡ chữ < 20 pt)
  eslint.config.js          ESLint 9 flat config
  src/
    theme/tokens.ts         cỡ chữ (pt → px), vùng bấm 56 px, 6 màu gọi tên được, khoảng cách
    theme/contrast.ts       tương phản WCAG (kiểm ≥ 7:1 trong test)
    i18n/vi.ts              mọi chữ trên giao diện, không thuật ngữ (test đối chiếu guardrails.yaml)
    api/client.ts           fetch tới /v1, Bearer từ bộ nhớ, join/login/ask/intakeCheck, lỗi → ApiError
    api/types.ts            kiểu khớp hợp đồng C6 (AskOut, IntakeCheckOut, Citation…)
    state/session.ts        mã đăng nhập + vai trò, chỉ trong bộ nhớ (useSyncExternalStore)
    hooks/useHashRoute.ts   #hoi-thu-tuc, #can-bo, còn lại là trang đầu
    components/             BigButton, VoiceBar, Subtitle, SimBadge, icons, ExpandableText (Xem đủ)
    screens/                AskScreen, AnswerCard, SourcePanel, DocumentsCard, OfficerScreen, OfficerLogin
    App.tsx                 khung chung (nhãn mô phỏng, tiêu đề, chân trang), trang đầu, vào lớp ?lop=
  tests/                    vitest: token, tương phản, App/điều hướng, component, client, i18n, AskScreen,
                            OfficerScreen, DocumentsCard, ExpandableText
  e2e/                      Playwright 3 viewport + axe: smoke (trang đầu), ask (hỏi thủ tục + cán bộ, API giả)
  public/icons/             biểu tượng PWA (SVG tạm)
```

## Nguyên tắc giao diện (bắt buộc, có test)

- Cỡ chữ cơ sở = `ui.min_font_pt` (20 pt = 26,67 px); thang chữ chỉ có `base/lg/xl/2xl/3xl`; `text-sm`, `text-xs` **không tồn tại**.
- Vùng bấm ≥ `ui.min_tap_px` (56 px) qua lớp `min-h-tap` / `min-w-tap`.
- Sáu màu có tên: `xanh`, `do`, `vang`, `xam`, `trang`, `den`; mọi cặp nền/chữ trong `contrastPairs` đạt ≥ 7:1.
- Tối đa **một** nút chính (màu xanh) mỗi màn hình; "Nói lại" và "Gọi tình nguyện viên" luôn hiện.
- Không CSS inline (ESLint chặn `style=`); không thuật ngữ (test đối chiếu `config/guardrails.yaml: banned_terms`).
- Mọi thay đổi ngưỡng đi qua `config/app.yaml`, không sửa số trong mã.

## Biến môi trường

`VITE_API_BASE` (xem `.env.example`): gốc API, mặc định `/v1`. Dev server chuyển tiếp `/v1` sang `http://localhost:<ports.api>`.

## Kiểm thử e2e

`e2e/ask.spec.ts` giả lập `/v1/**` bằng `page.route` (chỉ trong test; bản quay demo chạy với API thật ở `e2e/demo/`), dữ liệu giả ghi rõ "dữ liệu thử". Ngoài axe (không lỗi serious/critical) còn kiểm luật `color-contrast-enhanced` (≥ 7:1), cỡ chữ ≥ 20 pt của mọi phần tử có chữ và vùng bấm ≥ 56 px của mọi nút, liên kết, ô nhập, ô đánh dấu. Ảnh chụp để duyệt (chỉ viewport 390×844) ghi vào `docs/screens/<ngày>/<ngày>-P5-*.png`.

Giá trị giả trong test (mã lớp, mật khẩu thử) không viết dạng `khóa: 'chuỗi'` để gitleaks (`generic-api-key`) không bắt nhầm; vd `SAMPLE_CLASS_CODE` được ghép lúc chạy trong `tests/App.test.tsx`, `tests/client.test.ts`.

`pnpm e2e` tự khởi động Vite dev server ở cổng `ports.web`. Phiên bản `@playwright/test` được ghim (1.62.0) để trùng Chromium đã cài trên máy dev; đổi phiên bản thì chạy lại `pnpm exec playwright install chromium`. Báo cáo HTML ở `apps/web/playwright-report/` (gitignore).
