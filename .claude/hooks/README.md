# `.claude/hooks/` — hook Claude Code bằng Python (brief D2, D4, D20–D23)

Mọi hook là script Python **chỉ dùng thư viện chuẩn** (không cần `.venv`, không jq), gọi qua `bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh" <tên> [args]`. `run.sh` chọn `python3` (≥ 3.10) rồi `python`, `exec` file `.py` cùng tên và chuyển thẳng JSON hook trên stdin. Mã dùng chung ở `_common.py` (đọc stdin, mask secret, git, sha256, ghi JSONL). Chạy giống nhau trên Windows Git Bash và Linux.

Quy ước thoát: `exit 0` bình thường; `exit 2` + lý do tiếng Việt trên stderr = **chặn** (Claude Code hủy hành động và thấy lý do). `guard` và `protect-paths` **fail-closed**: dữ liệu hook không đọc được (stdin rỗng, JSON hỏng, thiếu `command`/`file_path`) → exit 2. Mọi hook khác **fail-open**: lỗi → exit 0 + ghi chú stderr (không bao giờ khóa phiên), trừ `promptlog` thiếu `transcript_path` → exit 1 có lý do (không im lặng — prompt log là minh chứng BTC).

## Bảng hook (khớp `settings.json`)
| Sự kiện | Matcher | Hook | Làm gì | Ghi vào |
| --- | --- | --- | --- | --- |
| SessionStart | – | `session-start.py` | In đầu `DAILY.md`, `CHECKPOINT.md`, tóm tắt `last_check.json`; cảnh báo nếu còn `.claude/BOOTSTRAP`; tự kiểm Python + `docs/prompt-log/` ghi được (cảnh báo lớn nếu không); nhập transcript ≤ 2 ngày từ `~/.claude/projects/<slug>/` chưa có trong INDEX | `docs/prompt-log/sessions/`, `INDEX.md` (status `imported`) |
| UserPromptSubmit | – | `prompt-guard.py` | Chặn prompt chứa secret (`sk-…`, `ghp_…`, `hf_…`, `AKIA…`, `password=…`, base64 ≥ 40 sau key/secret/token, private key, JWT); ghi prompt đã che | `docs/status/prompts.log` (gitignore) |
| PreToolUse | `Bash` | `guard.py` (+ `budget.py`) | Chặn lệnh phá hủy/rò rỉ (bảng dưới); trigger ngân sách `^(make (train\|data\|finetune)\b\|uv run (python )?-m ctcv_training\|uv run python training/)` → `budget.py` đọc `training/budget.json` (tạo mặc định nếu thiếu), chặn khi > 20 giờ GPU/job hoặc > 500.000 đ API/tác vụ (hoặc vượt tổng) | – |
| PreToolUse | `Edit\|MultiEdit\|Write\|NotebookEdit` | `protect-paths.py` | Chặn ghi `docs/prompt-log/**`, `data/registry/*.lock`, `docs/dossier/private/**`, migration đã có trên `main` (`git cat-file -e main:<path>`; không có HEAD → cho), `config/eval.yaml` (trừ `CTCV_ALLOW_EVAL_THRESHOLD=1` hoặc chưa có trên main), `.claude/**`/`CLAUDE.md`/`.github/workflows/**`/`.pre-commit-config.yaml`/`Makefile` (trừ khi có `.claude/BOOTSTRAP`); luôn cho `eval/redteam/**`, `docs/security/**`, `.claude/agent-memory/**` | – |
| PostToolUse | `Edit\|MultiEdit\|Write\|NotebookEdit` (timeout 120) | `format.py` | Chỉ `ruff format` cho `.py`; `prettier --write` cho `.ts/.tsx/.css/.json` dưới `apps/` khi có `apps/web/node_modules`; **không** `--fix`, **không** pytest (D23); lỗi trả về Claude qua `additionalContext` | – |
| PostToolUseFailure | `Bash` | `notify.py` | Ghi lệnh (đã che secret) + lỗi | `docs/status/errors.log` |
| SubagentStop | – | `subagent-log.py` | Ghi `{ts, session_id, agent_id, agent_type, summary ≤ 200 ký tự}`; chép `agent_transcript_path` (hoặc `transcript_path` của subagent) | `docs/status/subagents.log`, `docs/prompt-log/subagents/<session>-<agent>.jsonl` |
| PreCompact | – | `checkpoint.py` | Ghi đè "Checkpoint gần nhất" (thời điểm, session, nhánh/HEAD, epic, file đang đổi, make check gần nhất), đẩy bản cũ vào "Lịch sử" (≤ 10), giữ "Ghi chú tay" | `docs/status/CHECKPOINT.md` |
| Stop | – | `promptlog.py` | Chép `transcript_path` → `docs/prompt-log/sessions/<session_id>.jsonl` (ghi đè idempotent, **không** đụng INDEX) | `docs/prompt-log/sessions/` |
| Stop | – | `daily.py` | Nhắc (không chặn, D4) khi có thay đổi dưới `services/ apps/ sandbox/ drills/ libs/` mới hơn `last_check.json`; cập nhật mục "Phiên gần nhất" trong `DAILY.md`; luôn exit 0 (`make daily` pipe `{}`) | `docs/status/DAILY.md` |
| SessionEnd | – | `promptlog.py --close` | Chép lần cuối, SHA-256, **một** dòng/phiên trong `INDEX.md` (`\| ts \| file \| sha256 \| git_head \| status \|`), chỉ mục transcript subagent của phiên, snapshot `system/<session_id>.json` = hash của `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/*.md`, `.claude/skills/**/SKILL.md`, `config/prompts/*.md` + git HEAD | `docs/prompt-log/INDEX.md`, `system/` |
| (Makefile) | – | `promptlog.py --sync` | `make promptlog-sync`: nhập **mọi** transcript trong `~/.claude/projects/<slug>/` chưa có trong INDEX (slug = cwd với `:` và `\`/`/` → `-`, thử cả hai kiểu chữ đầu; `CLAUDE_CONFIG_DIR` được tôn trọng; bỏ qua phiên hiện tại qua `CLAUDE_SESSION_ID`) | như trên, status `imported` |

## `guard.py` chặn gì (D22; test có biến thể vòng qua)
`rm` với cờ r+f mọi thứ tự/spelling (`-rf`, `-fr`, `-r -f`, `--recursive --force`, `sudo`, `/bin/rm`, qua `xargs`), `Remove-Item -Recurse -Force`, `rd /s`, `del /s|/q` · `git push --force|-f|--force-with-lease`, refspec `+ref` · `git reset --hard origin|upstream` · `git clean -f` (không `-n`) · `git commit --no-verify|-n`, `SKIP=… git commit`, `pre-commit uninstall` · `git -c core.hooksPath`, `git config core.hooksPath` · `docker system|volume prune` · `docker compose config` không `--no-interpolate` · `printenv`, `env`/`set`/`export` đứng một mình, `$(env)`, `echo $…TOKEN|SECRET|PASSWORD…`, `print(os.environ)`, `ls env:` · `mkfs`, `format x:`, `dd of=/dev/`, fork bomb · `curl|wget … | sh|bash|python|iex` · đọc `.env`/`.env.*`/file ẩn glob/`*.pem`/`id_rsa` qua `cat/less/more/head/tail/grep/awk/sed/cut/sort/od/xxd/strings/type/Get-Content/Select-String/source/python -c/node -e`, `< .env` · ghi/xóa `docs/prompt-log/**`, `data/registry/*.lock` bằng `rm/mv/cp/tee/sed -i/redirect`. Cho phép: `cp .env.example .env`, `ls`, `test -f .env`, `docker compose --env-file .env up`, `env VAR=1 cmd`, `set -euo pipefail`, `git commit -m 'handle -n option'`, `ssh -i x.pem`.

## Chạy tay / gỡ lỗi
```
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf build"}}' | bash .claude/hooks/run.sh guard; echo "exit=$?"
echo '{"tool_name":"Write","tool_input":{"file_path":"docs/prompt-log/INDEX.md"}}' | bash .claude/hooks/run.sh protect-paths
echo '{}' | bash .claude/hooks/run.sh daily            # = make daily
bash .claude/hooks/run.sh promptlog --sync             # = make promptlog-sync
```
Trường có trong JSON hook: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `tool_name`, `tool_input{command|file_path|content}`, `prompt`; SubagentStop thêm `agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message`. Gốc repo = `$CLAUDE_PROJECT_DIR`, rồi `cwd` trong JSON, rồi hai cấp trên thư mục hook.

## Kiểm thử
```
uv run pytest .claude/hooks/tests -q
```
`tests/test_hooks.py` chạy **mỗi hook như subprocess với JSON trên stdin** trong thư mục tạm (≥ 25 ca, gồm biến thể vòng qua, fail-closed, idempotent, sync), kiểm frontmatter YAML của mọi agent/skill, hợp đồng `settings.json`, `.mcp.json`, `CLAUDE.md` ≤ 150 dòng, marker `BOOTSTRAP`. `tests/test_sync_plugin.py` kiểm `scripts/sync_plugin.py` và `plugins/ctcv-kit` đang đồng bộ. Thư mục này chưa nằm trong `testpaths` của root `pyproject.toml` (gói A không sở hữu file đó) — integrator nối vào `make check`. Lint: `uv run ruff check .claude/hooks && uv run ruff format --check .claude/hooks` (ruff `--fix` không được chạy trong hook format — D23).
