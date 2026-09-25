# Kiểm tra bảo mật trước khi công khai repo CTCV — 25/9/2026

Người kiểm: security-redteam (chỉ đọc; không sửa mã sản phẩm, hook, `.gitignore` hay cấu hình). Mục đích: đưa
toàn bộ repo lên GitHub ở chế độ **công khai** để dán link vào ô "Link sản phẩm dùng thử" của form Data for Life
2026 (đề DA940-01). Báo cáo **không** chứa giá trị bí mật nào: mọi secret/PII chỉ được nêu bằng loại, số lượng, vị
trí và độ dài.

## 1. Kết luận

- **Bộ 848 file ban đầu (`git add -A -n`, 94,4 MB, trong đó `docs/prompt-log/` ≈ 81,8 MB): CHẶN.** Transcript thô
  chứa một mật khẩu cơ sở dữ liệu thật (của một dự án khác, không thuộc CTCV) mà gitleaks không phát hiện, gmail cá
  nhân của chủ repo và dữ liệu của các dự án khác trên máy.
- **Bộ 787 file sau khi orchestrator sửa `.gitignore` theo phương án (b)** (≈ 13,1 MB; `docs/prompt-log/` chỉ còn
  `INDEX.md` + `README.md`; bỏ `.playwright-mcp/`, `ctcv-dev.db`): quét lại **sạch**. gitleaks chỉ còn 1 phát
  hiện, là giá trị giả trong test hook. Quét che giá trị cho kết quả 0 gmail, 0 URL có mật khẩu, 0 khóa Supabase,
  0 thông tin đăng nhập demo, 0 đường dẫn máy.
- Công khai được sau khi xử lý **4 blocker ở §8**. Blocker B1 (đổi mật khẩu) phải làm **ngay**, dù có công khai
  repo hay không.

## 2. Bảng lỗ hổng

| # | Mức | Phát hiện | Tái hiện, bằng chứng | Đề xuất | Test hồi quy cần có |
| --- | --- | --- | --- | --- | --- |
| V1 | P1 | Mật khẩu Postgres thật (16 ký tự) của một project Supabase **khác**, kèm mã project và 2 khóa `sb_publishable_`. | Nằm ở `docs/prompt-log/sessions/2d228d6b-…jsonl` dòng 157 (18/9). Lệnh "Check Docker…, git identity and global Claude settings" đã in `~/.claude/settings.json`, trong đó có luật allow của dự án khác chứa URL kết nối. gitleaks 8.30 **không** bắt được (đã tái hiện với URL giả: "no leaks found"). Bản `docs/dossier/out/07_PromptLog.zip` (19/9) che **thiếu**: còn 14/16 ký tự. | Đổi mật khẩu ngay, xem log truy cập Supabase, đổi ở mọi nơi dùng lại mật khẩu hoặc biến thể của nó. Không công khai và không gửi transcript thô hay zip 19/9. | `tests/config/test_gitleaks_rules.py`: nạp `.gitleaks.toml`, khẳng định luật mới khớp `postgresql://u:<giả>@db.x.supabase.co` và `sb_secret_…` giả. |
| V2 | P1 | PII và dữ liệu riêng trong transcript thô. | gmail cá nhân chủ repo xuất hiện 98 lần trong 49 file (51 bản ghi `attachment.session_context`). `organizationUuid` của tài khoản có trong 36 bản ghi. 78 bản ghi `environment` liệt kê thư mục dự án khác (788 lượt). Bản dump settings toàn cục chứa 1 SĐT dạng thật của bên thứ ba cùng lệnh của các dự án khác. Tên người dùng Windows là "Admin" (1.958 lượt), chung chung, rủi ro thấp. | Áp dụng phương án (b) (đã làm trong `.gitignore`). | Kiểm `git ls-files docs/prompt-log` chỉ trả `INDEX.md`, `README.md` (thêm vào `scripts/check_docs.py` + test). |
| V3 | P2 | `make promptlog-export` che không đủ, nên phương án (c) chưa an toàn. | Thử `redact_text` bằng giá trị giả. URL có mật khẩu chứa `%` bị giữ nguyên tiền tố (mẫu e-mail chỉ nuốt đoạn `xx@host`). Không che `officer_password`, `?lop=`, `sb_publishable_…` và danh sách thư mục. | Che toàn bộ userinfo của URL; che khóa JSON `*password*`/`*token*`, tham số `lop`, `sb_*`, `session_context`, `environment`, `credential_org`; quét lại sau khi che, còn khớp thì dừng. | `scripts/tests/test_promptlog_export.py`: 5 ca giả; khẳng định không còn chuỗi con ≥ 4 ký tự của mật khẩu giả. |
| V4 | P2 | Cấu hình quét secret có điểm mù. | Luật mặc định không có mẫu cho mật khẩu trong URL và khóa Supabase. `.gitleaks.toml` bỏ qua `docs/prompt-log/` với luật e-mail/SĐT, bỏ qua toàn bộ `eval/sets/`. Neo `^docs/` chỉ chạy đúng khi `--source .` (đường dẫn tuyệt đối làm luật riêng im lặng). | Thêm luật `ctcv-url-credentials` và `supabase-secret-key` (sửa qua ADR vì `.gitleaks.toml` là điểm dừng). | Như V1. |
| V5 | P2 | Hook `guard` cho qua các lệnh rủi ro khi công khai. | Chạy `echo '<json>' \| bash .claude/hooks/run.sh guard`. Cho qua (allow): `cat ~/.claude/settings.json` (đúng đường lộ V1), `git add -f docs/prompt-log/sessions/…`, `git add -A -f`, `zip -r … docs/prompt-log`, `gh repo create --public --push`, `gh repo edit --visibility public`. Chặn đúng: `push --force`, `--no-verify`, `-c core.hooksPath`. | Thêm luật chặn đọc `~/.claude/settings*.json` và `~/.claude.json`, chặn `git add -f` vào `docs/prompt-log/{sessions,subagents,system}`; đặt quyền `ask` cho `gh repo create`/`gh repo edit --visibility`. | `.claude/hooks/tests/test_hooks.py`: 4 ca (đọc settings toàn cục, force-add prompt-log, zip prompt-log, đổi visibility). |
| V6 | P2 | `.claude/BOOTSTRAP` vẫn nằm trong bộ commit. | `protect-paths.py` dòng 89–94: còn marker thì **không** bảo vệ `.claude/**`, `CLAUDE.md`, `.github/workflows/**`, `Makefile`, và mọi bản clone đều nhận marker này. | Xóa trước commit đầu (CLAUDE.md bắt buộc). Đây là điểm dừng, người dùng tự làm. | Test: trên `main` không tồn tại `.claude/BOOTSTRAP`. |
| V7 | P3 | Thông tin đăng nhập demo tạm bị in vào transcript. | Phiên 42a8ed58, dòng 726, 811, 1054, 1258: 3 mật khẩu cán bộ 24 ký tự và 3 mã lớp `?lop=`. Chỉ dùng trên 127.0.0.1, sinh mới mỗi lượt, đã hết hạn. | Không in secret. `dev_cpu.py` chỉ in khi có `--show-credentials`, còn script tạm thì đã in ra. | Test: `dev_cpu.banner(show_credentials=False)` không chứa giá trị secret. |
| V8 | P3 | `gate.yml` chạy trên self-hosted runner khi PR được gắn nhãn `needs-gpu`; repo công khai thì PR từ fork có thể chạy mã trên máy GPU. | `.github/workflows/gate.yml` dòng 19–34. | Bật "Require approval for all outside collaborators". Không gắn nhãn cho PR từ fork, hoặc bỏ trigger `pull_request`. | — (kiểm tay trong Settings) |
| V9 | P3 | INDEX prompt-log chưa khớp. | Phiên 42a8ed58 (đang chạy) lệch SHA-256; 32 file subagent chưa có trong INDEX. | Commit lại `INDEX.md` sau khi phiên đóng (`--close`/`make promptlog-sync`). | `check_docs`: mọi dòng INDEX có file thì hash phải khớp. |
| V10 | P3 | Phân phối và tài liệu chưa khớp phương án (b). | `NOTICE` dòng 7 ghi "development history is published in docs/prompt-log/", nay sai. `NOTICE` ghi không phân phối lại dữ liệu nhưng repo có 4 HTML cắt gọn + 3 bản ghi fixture (có ghi nguồn). `docs/template/AI2026_Mau_ho_so.docx` là mẫu của BTC cuộc thi cũ, metadata có tên người bên thứ ba. Dòng `build/` của `.gitignore` loại luôn `docs/dossier/build/**` (script + test của `make dossier`). | Sửa NOTICE. Gỡ docx (phải sửa `scripts/doctor.py`) hoặc giữ kèm ghi nguồn. Thêm `!docs/dossier/build/` (đã quét, sạch). | — |

## 3. gitleaks trên đúng tập sẽ commit

Lệnh theo yêu cầu: `gitleaks detect --no-git --source <pubcopy>`, chạy thêm hai cấu hình (`--source .` với
`.gitleaks.toml`, và chỉ bộ luật mặc định). Cả ba đều ra **14 phát hiện**, cùng một danh sách:

| Loại | Số | Vị trí | Phân loại |
| --- | --- | --- | --- |
| `api_key: QUJD…` (base64 của "ABCDEFG…") | 2 | `.claude/hooks/tests/test_hooks.py:403` và bản in lại trong 1 transcript | giá trị giả trong test |
| `qr_token: 'lop-…01'` (hằng mẫu của test web) | 8 | 4 transcript subagent | giá trị giả trong test |
| `tokenCsrf` của trang cổng DVC Bộ Công an (phiên ẩn danh) | 4 | 2 transcript subagent | nhiễu |
| **Bí mật thật** | **0 phát hiện** | — | nhưng **bỏ sót 1 bí mật thật** (V1) |

Sau khi sửa `.gitignore` (787 file) còn đúng 1 phát hiện: `test_hooks.py:403`, giá trị giả.

## 4. Quét PII và thông tin riêng (848 file; JSONL được giải mã và quét từng chuỗi)

| Loại | Trong file mã/tài liệu | Trong `docs/prompt-log/` thô |
| --- | --- | --- |
| E-mail | 9 lần, toàn `@example.*` hoặc hộp thư công khai | gmail chủ repo ×98, `noreply@anthropic` ×94, e-mail cơ quan công khai (cổng DVC, BTC), `@example` |
| SĐT | 4 số giả (0912345678…) | 12 số khác nhau: đều giả, hoặc là mảnh UUID/số thực, trừ **1 SĐT dạng thật của bên thứ ba** (V2) |
| CCCD 12 số | 4 số giả | 7 số khác nhau: giả hoặc đuôi UUID; **0 số thật** |
| Số thẻ (qua kiểm Luhn) | 4111…1111 (thẻ test) | 4 số hợp lệ Luhn: số test, 0000…, mảnh định danh dài; **0 thẻ thật** |
| Token/khóa (`sk-ant`, `ghp_`, `hf_`, `AKIA`, `sk-proj`) | chỉ giá trị giả trong test hook | chỉ bản in lại của giá trị giả |
| JWT, khóa riêng, cookie phiên đăng nhập | 0 | 0 (2 `Set-Cookie` là header phản hồi ẩn danh của cổng DVC) |
| Link Google Drive/Docs | 1 placeholder | mẫu hồ sơ BTC (công khai), placeholder test, form của cổng DVC |
| Đọc `.env` | 0 | 0 lần lộ nội dung (10 lệnh có nhắc `.env`: kiểm tồn tại hoặc grep khóa, 3 lệnh bị hook chặn) |
| Ảnh chụp màn hình | Xem 7/41 ảnh và ảnh ghép khung video: chỉ có giao diện mô phỏng và thủ tục công khai, ô mật khẩu rỗng. Chưa xem từng khung của `docs/media/demo-preview.gif`, chỉ xem ảnh ghép khung của video nguồn. | — |

`docs/dossier/private/team.example.yaml` bị luật `deny` chặn đọc. Quét tự động chỉ thấy nhãn trường và 1 link Drive
dạng placeholder, không có e-mail hay SĐT. Chủ repo nên tự mở xác nhận.

## 5. Giấy phép và phân phối

- `data/raw`, `data/clean`: chỉ có `.gitkeep`. Không có trọng số mô hình (`*.gguf`, `*.safetensors`… đã gitignore).
- `data/tests/fixtures/tthc/*.html`: 4 trang cắt gọn, có chú thích nguồn và ngày tải, đã bỏ script, form đăng nhập
  và chân trang. Cách làm này hợp điều kiện "ghi rõ nguồn" ở chân trang cổng DVC. Cần sửa câu trong NOTICE (V10).
- `eval/sets/samples`: 130 + 83 dòng; câu hỏi dài nhất 283 ký tự; `expected_values` dài nhất 64 ký tự; mọi dòng có
  `source`. Không có trích đoạn dài.
- `docs/template/AI2026_Mau_ho_so.docx`: **không nên công khai**. Đây là mẫu của BTC cuộc thi cũ, không có giấy phép
  phân phối lại, và DFL không cần. Nếu gỡ thì sửa `scripts/doctor.py` (đang kiểm file này tồn tại).
- Không có file nào > 12 MB. Video và PDF nằm ở `docs/dossier/out/` (đã gitignore). GIF README 3,3 MB.

## 6. `.gitignore`

Orchestrator đã thêm và tôi đã kiểm bằng `git check-ignore`: `docs/prompt-log/{sessions,subagents,system}/`,
`ctcv-dev.db`, `*.db-journal`, `.playwright-mcp/`. Đề xuất thêm:

```gitignore
*.db
*.sqlite
*.sqlite3
*.mp4
*.webm
*.mp3
*.wav
!**/tests/fixtures/**/*.wav
*.zip
*.bak
/tmp/
/scratch/
# đặt sau dòng `build/` để script dựng hồ sơ và test được commit (đã quét: sạch)
!docs/dossier/build/
```

## 7. Ba phương án cho `docs/prompt-log/`

| Phương án | Rủi ro |
| --- | --- |
| (a) Công khai toàn bộ | Lộ V1 (secret thật) và V2 (gmail, UUID tổ chức, thư mục và lệnh của dự án khác, SĐT bên thứ ba). Kèm theo: thông tin đăng nhập demo đã hết hạn, bản sao nguyên văn trang web bên thứ ba, repo nặng thêm ≈ 82 MB, INDEX lệch hash (trông như bị sửa). DFL không đòi prompt log công khai. **Loại.** |
| (b) Chỉ `INDEX.md` (SHA-256) + README; transcript thô giữ riêng, đưa BTC khi được yêu cầu | Không lộ. Hash vẫn là cam kết toàn vẹn (commit có dấu thời gian). Cần chốt INDEX sau khi phiên đóng (V9), sửa NOTICE và README prompt-log (README chỉ người dùng sửa được). Trước khi gửi BTC: đổi secret V1 và gửi bản đã che bằng công cụ đã sửa (V3). **Khuyến nghị; đã áp dụng.** |
| (c) Công khai sau khi lọc | Sửa file thì hash lệch với INDEX, dễ bị hiểu là làm giả; phải công bố cả hash gốc lẫn hash sau che. Công cụ che hiện tại sót (V3), gitleaks mù (V4): 82 MB JSON khó bảo đảm che đủ. Chỉ nên làm khi V3, V4 đã sửa và có test. |

## 8. Blocker (bắt buộc trước khi công khai)

1. **B1**: đổi mật khẩu Postgres của project Supabase bị lộ ở V1, xem log truy cập, đổi ở nơi dùng lại mật khẩu
   hoặc biến thể. Không gửi `07_PromptLog.zip` (19/9) cho ai; nếu từng đặt quyền công khai trên Drive thì gỡ.
2. **B2**: commit chỉ chứa `docs/prompt-log/INDEX.md` + `README.md`. Kiểm ngay trước commit bằng
   `git add -A -n | grep prompt-log` và sau commit bằng `git ls-files docs/prompt-log`. Không dùng `git add -f`,
   vì hook hiện không chặn (V5).
3. **B3**: xóa `.claude/BOOTSTRAP` trước commit đầu (V6; điểm dừng, người dùng tự làm).
4. **B4**: sửa `NOTICE` dòng 7 cho khớp phương án (b). Thể lệ DFL cấm mô tả sai.

## 9. Đã thử gì (bề mặt × kỹ thuật)

| Bề mặt | Kỹ thuật | Kết quả |
| --- | --- | --- |
| Tập file sẽ commit (848, rồi 787) | gitleaks theo 3 cấu hình; regex 25+ dạng token; userinfo URL; `key=value` | V1, V4 |
| Transcript JSONL | Giải mã đệ quy mọi chuỗi; phân theo loại bản ghi (`attachment`, `tool_result`, `thinking`) | V1, V2, V7 |
| Tool đọc ngoài repo | Trích mọi đường dẫn trong `tool_use` | `~/.claude/settings.json` bị in 1 lần (V1) |
| `.env`, `private/` | Truy vết `tool_use` và kết quả | Không lộ nội dung |
| Công cụ che (`promptlog_export`) | Thử bằng giá trị giả | V3 |
| Hook `guard` | 11 lệnh liên quan công khai qua `run.sh guard` (JSON trên stdin) | V5 |
| Quản trị | Đọc `protect-paths.py`, workflow, git identity (noreply ✔), INDEX hash | V6, V8, V9 |
| Nhị phân | 7 ảnh PNG, metadata docx, kích thước sqlite | V10; ảnh sạch |
| Guardrail sản phẩm | `python -m ctcv_eval.redteam --report-dir <scratchpad>` (không ghi `eval/reports`) | **92/92 đạt, 0 rò rỉ** |

Kịch bản red-team mới: **0**, vì bản kiểm này không có diff guardrail, tool hay prompt, và phạm vi chỉ được ghi
báo cáo. Test hồi quy cần có ghi ở cột cuối §2.

## 10. Tự khai sự cố trong lúc kiểm

Khi in ngữ cảnh quanh URL kết nối lấy từ zip 19/9 (đã che một phần), regex che của tôi dựa vào ký tự `@`, mà ký
tự này đã bị token che nuốt mất. Hậu quả: 14 ký tự đầu của mật khẩu V1 bị in vào transcript subagent của phiên
kiểm này. Transcript đó sẽ nằm ở `docs/prompt-log/subagents/42a8ed58-…jsonl`, thư mục đã gitignore. Không lặp lại
giá trị ở đâu khác. Đây thêm một lý do cho B1 và B2. Bài học đã ghi vào memory của security-redteam: che theo cấu
trúc trước khi cắt ngữ cảnh.
