# docs/prompt-log — Prompt Log (minh chứng bắt buộc của BTC)

BTC (FAQ, `docs/competition/BTC-2026-yeu-cau.md` §4): Prompt Log là "lịch sử câu lệnh (prompt) giao tiếp với công cụ AI, bao gồm System Prompt và toàn bộ conversation history. Bắt buộc nộp kèm hồ sơ dự án"; "Làm giả Prompt Log hoặc lịch sử commit" bị nghiêm cấm; mục 13 MẪU 3 đòi **link thư mục Google Drive đã mở quyền** chứa lịch sử câu lệnh + ảnh minh chứng + tài liệu kỹ thuật + mã nguồn.

## Quy tắc (không có ngoại lệ)
1. **Chỉ hook ghi, không ai sửa tay.** Thư mục này do hook Claude Code (`.claude/hooks/promptlog.py`, `subagent-log.py`, `session-start.py`) ghi; `settings.json` deny `Edit/Write/MultiEdit(docs/prompt-log/**)`, hook `protect-paths` chặn, `guard` chặn lệnh Bash ghi vào đây. Phiên lỗi cũng được ghi (plan §3). Nếu phát hiện file lệch hash → không "sửa cho khớp"; ghi sự cố vào `docs/ops/incidents.md` và giữ nguyên.
2. **Một file mỗi phiên** (D20): `sessions/<session_id>.jsonl` — hook `Stop` chép transcript idempotent sau mỗi lượt (ghi đè cùng file, **không** đụng INDEX); hook `SessionEnd` chép lần cuối, tính SHA-256, ghi **một dòng** vào `INDEX.md`, và lưu snapshot "system prompt" vào `system/<session_id>.json` (hash + nội dung của `CLAUDE.md`, `.claude/agents/*`, `.claude/skills/**`, `.claude/settings.json`, `config/prompts/*` theo git HEAD lúc đó).
3. **Subagent**: hook `SubagentStop` chép `agent_transcript_path` (nếu có) vào `subagents/<session_id>-<agent>-<n>.jsonl` và lập chỉ mục ở SessionEnd.
4. **INDEX.md**: bảng `| ts | file | sha256 | git_head | status |` — `ts` UTC ISO, `file` đường dẫn tương đối thư mục này, `sha256` của file lúc ghi, `git_head` (`git rev-parse --short HEAD` hoặc `nogit`), `status` `open|closed|imported`. Một dòng/file; `make docs-check` chỉ kiểm INDEX hợp lệ và hash khớp (N12), không đòi "phiên hiện tại đã có log" (log phiên hiện tại chỉ có ở SessionEnd).
5. **Commit mỗi ngày**: `docs/prompt-log/` được commit cuối ngày (`/daily` nhắc) để git history là bằng chứng toàn vẹn thứ hai ngoài INDEX (SEC-14). `.gitignore` không bao giờ bỏ qua thư mục này.
6. **Công cụ AI ngoài Claude Code** (N14): `tools/` lưu prompt template + tham số + mẫu đầu ra của bước sinh dữ liệu / LLM-judge (E06) và mọi lần gọi API LLM; `pre-D1/` chứa các hội thoại đã soạn `docs/idea.md`, `docs/plan.md`, `docs/prompt.md` (người dùng xuất tay, PDF/Markdown, đặt tên `YYYY-MM-DD-<công cụ>-<chủ đề>`), để chuỗi minh chứng không có khoảng trống.
7. **System prompt**: phần system prompt nội bộ của Claude Code do Anthropic quản lý và không xuất được; những gì đội kiểm soát (CLAUDE.md, agents, skills, settings, config/prompts) được snapshot theo phiên trong `system/`; README trong Drive giải thích các tầng này cho giám khảo.

## Phiên chạy trước khi có hook (bộ nhập ở đầu phiên)
`session-start.py` (và `make promptlog-sync`) quét `~/.claude/projects/<slug>/*.jsonl`, nhập mọi transcript chưa có trong INDEX vào `sessions/` với `status: imported` và hash lúc nhập — bù cho phiên E01 đầu tiên và phiên rà soát 18/9 nếu chúng chạy trước khi hook được cài (S10, CF-04). Chạy `make promptlog-sync` ngay sau khi cài hook và trước mỗi lần xuất.

## Xuất ZIP và đồng bộ Google Drive (mục 13 MẪU 3)
1. `make promptlog-sync` — nhập phiên thiếu.
2. `make promptlog-export` (`scripts/promptlog_export.py` + redaction gate D21): kiểm mọi file trong INDEX tồn tại và hash khớp (lệch → dừng, không xuất); chạy gitleaks + regex PII (`config/guardrails.yaml`) trên toàn bộ thư mục; phát hiện → thay bằng `[REDACTED-SECRET sha256:<8>]` / `[REDACTED-PII sha256:<8>]` trong **bản sao** đem công bố và ghi `REDACTIONS.md` (đây là **chính sách công bố**, không phải sửa log; bản gốc trong thư mục này và hash trong INDEX giữ nguyên); tạo `docs/dossier/out/07_PromptLog.zip` + `.sha256` + `07_PromptLog.zip.REDACTIONS.md`. Đó là toàn bộ những gì script làm ở E01.
3. Cây `drive/` (7 thư mục, khớp bảng mục 13 trong `docs/dossier/src/13-lich-su-cau-lenh.md`) **chưa được script dựng**: epic DOSSIER sẽ thêm cờ `make promptlog-export --drive` để dựng vào `docs/dossier/out/drive/` từ bản sao đã redaction và kết quả `make evidence`. Tới khi đó, người dùng tạo tay đúng cấu trúc sau:
   - `01-prompt-log/` (JSONL gốc + bản Markdown dễ đọc mỗi phiên + `INDEX.md` + `pre-D1/`)
   - `02-system-prompts/` (`system/*.json`)
   - `03-subagent-transcripts/`
   - `04-minh-chung-theo-ngay/` (`docs/screens/YYYY-MM-DD/` + snapshot `DAILY.md` từ `make evidence`)
   - `05-tai-lieu-ky-thuat/` (ADR, README, `eval/reports`)
   - `06-ma-nguon/` (link repo + zip tag)
   - `07-prompt-cong-cu-khac/` (`tools/` — prompt sinh dữ liệu / LLM-judge, N14)
   - `README.md` (giải thích tầng system prompt, quy tắc redaction, cách kiểm hash)
4. Người dùng upload `drive/` lên thư mục Google Drive của đội (rclone `rclone sync drive/ gdrive:CTCV-AI2026/` hoặc kéo thả), đặt quyền **Anyone with the link – Viewer**, mở thử ở cửa sổ ẩn danh, điền `drive_url` trong `docs/dossier/private/team.yaml` (placeholder `{{team:drive_url}}` của `docs/dossier/src/13-lich-su-cau-lenh.md`) và ghi vào `05_Repo.txt`.
5. Drive **không** chứa: `docs/dossier/private/`, `.env`, dữ liệu pilot thô, audio, ảnh app thật.

## Bảng redaction
`scripts/promptlog_export.py` không sửa thư mục này: bản đã redaction chỉ nằm trong ZIP (và cây `drive/` khi có), còn bảng redaction (file, số lần, hash trước/sau) được ghi vào `REDACTIONS.md` **bên trong** ZIP và cạnh nó (`docs/dossier/out/07_PromptLog.zip.REDACTIONS.md`); INDEX của bản gốc giữ hash gốc. Cả hai file này được đưa lên Drive cùng `01-prompt-log/` để giám khảo đối chiếu.

## Cấu trúc thư mục
```
docs/prompt-log/
  README.md        INDEX.md
  sessions/        <session_id>.jsonl          (hook Stop/SessionEnd)
  system/          <session_id>.json           (snapshot system prompt, SessionEnd)
  subagents/       <session_id>-<agent>-<n>.jsonl
  tools/           <YYYY-MM-DD>-<bước>-<model>.md   (prompt sinh dữ liệu / judge)
  pre-D1/          <YYYY-MM-DD>-<công cụ>-<chủ đề>.(md|pdf)  (người dùng xuất tay)
```
