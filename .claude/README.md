# `.claude/` — cấu hình Claude Code của CTCV (brief §11 v2, D17–D24)

Thư mục này là "bộ não cố định" mà Claude Code đọc mỗi phiên: quyền, hook, 10 subagent, 16 skill. Cùng với `CLAUDE.md` (≤ 150 dòng) và `.mcp.json` ở gốc repo, nó được commit để cả đội và CI dùng chung. **Sửa bất kỳ file nào ở đây chỉ qua ADR** — hook `protect-paths` chặn ghi vào `.claude/**`, `CLAUDE.md`, `Makefile`, `.github/workflows/**`, `.pre-commit-config.yaml` trừ khi còn marker `.claude/BOOTSTRAP` (chỉ tồn tại trong E01; xóa khi merge PR E01).

## Cấu trúc
```
.claude/
  settings.json                # model claude-fable-5-1, effortLevel xhigh, permissions allow/deny, hooks (D17–D24)
  settings.local.json.example  # mẫu cho settings.local.json (gitignore) — đường dẫn/quyền máy cá nhân
  BOOTSTRAP                    # marker E01: tắt bảo vệ cấu hình Claude Code/CI (xóa khi merge E01)
  README.md                    # file này
  agents/*.md                  # 10 subagent (+ eval-runner tùy chọn) — model: inherit, không background (D17–D19)
  skills/<tên>/SKILL.md        # 8 skill kiến thức (tự nạp) + 8 skill quy trình (gọi tay, disable-model-invocation)
  hooks/run.sh + *.py          # hook Python stdlib (D2); tests/ chạy bằng `uv run pytest .claude/hooks/tests`
  agent-memory/                # memory: project của architect/reviewer/security-redteam (Claude Code tự tạo)
```

## settings.json (tóm tắt)
- `"model": "claude-fable-5-1"`, `"effortLevel": "xhigh"`; **không** có `env` với `CLAUDE_CODE_SUBAGENT_MODEL` hay `CLAUDE_CODE_MAX_*` (không tồn tại trên CLI 2.1.119 — D3/D17). Giới hạn 6 subagent đồng thời / 2 tầng là luật trong `CLAUDE.md`.
- `enableAllProjectMcpServers: false`, `enabledMcpjsonServers: ["playwright"]` (D24).
- `permissions.defaultMode: acceptEdits`; allow: `make`, `uv`, `pnpm`, `npx`, `python`, `pytest`, `ruff`, `docker compose`, `git status/diff/log/add/commit/checkout -b/merge/worktree`, `git push origin epic/*`, `gh`, `mcp__playwright`; deny: `git push --force|-f`, `* --no-verify*`, `rm -rf`, `docker system prune`, `Read(.env)`, `Read(.env.*)`, `Read(**/*.pem)`, `Read(docs/dossier/private/**)`, `Edit/Write/MultiEdit(docs/prompt-log/**)`, `Edit/Write(data/registry/*.lock)`.
- Hooks: xem `hooks/README.md`. Mọi lệnh hook có dạng `bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh" <tên> [args]`.

## settings.local.json (không commit)
Chép `settings.local.json.example` → `settings.local.json` rồi thêm quyền/biến của máy mình (ví dụ `Bash(ssh gpu-box *)`, `VLLM_BASE_URL` trỏ máy GPU). Không đặt secret ở đây — secret chỉ trong `.env`/GitHub Secrets. `.gitignore` đã bỏ qua file này.

## Subagent (`agents/`, prompt.md §2 + brief D17–D19)
| Agent | Tools | Effort | Đặc biệt |
| --- | --- | --- | --- |
| architect | Read, Grep, Glob, WebFetch | max | `permissionMode: plan`, `memory: project`; trả nội dung ADR, không ghi file |
| backend-dev | Read, Edit, Write, Bash, Grep, Glob | xhigh | `isolation: worktree` (chỉ sau commit đầu), skills ctcv-conventions, fastapi-conventions |
| frontend-dev | như trên | xhigh | `isolation: worktree`, skills ctcv-conventions, elder-ui, mcp playwright |
| data-engineer | + WebFetch | high | skill data-pipeline; ngân sách API qua hook |
| ml-trainer | Read, Edit, Write, Bash | xhigh | skill training-runbook; hook budget chặn > 20 giờ GPU |
| qa-tester | Read, Edit, Write, Bash, Grep, Glob | high | skills test-strategy, ctcv-conventions; mcp playwright; **không** background (cổng đồng bộ) |
| security-redteam | Read, Grep, Glob, Bash, Write, Edit | max | `memory: project`; protect-paths chỉ cho ghi `eval/redteam/**`, `docs/security/**` |
| devops | Read, Edit, Write, Bash | high | `disallowedTools: Read(.env), Read(.env.*), Read(**/*.pem)` |
| reviewer | Read, Grep, Glob | xhigh | chỉ đọc (không Bash), `memory: project` |
| docs-writer | Read, Edit, Write, Bash | high | skill dossier-btc |
| eval-runner (tùy chọn) | Read, Bash | medium | `background: true` — chỉ chạy `make gate/eval` hằng đêm |
Tất cả `model: inherit` (kế thừa settings). Thân agent tiếng Việt ≤ 40 dòng: đầu vào, quy trình, định dạng đầu ra (≤ 40 dòng + đường dẫn), điều không bao giờ làm, ba nguyên tắc bất biến. Gọi: để Claude tự chọn theo `description`, hoặc `@agent-<tên>`.

## Skill (`skills/`)
- Tự nạp khi liên quan: `ctcv-conventions`, `fastapi-conventions`, `elder-ui`, `coach-style`, `data-pipeline`, `training-runbook`, `test-strategy`, `agent-security`.
- Gọi tay (`disable-model-invocation: true`, có `argument-hint`): `/epic E0X`, `/daily`, `/review E0X`, `/fix <lỗi>`, `/refactor <đường dẫn>`, `/incident <mô tả>`, `/dossier-btc [DRAFT=1|final|check]`, `/hackathon-kit [2-ngay|12-gio|dien-tap]`.

## MCP (`.mcp.json`, D24)
Chỉ `playwright`. Trên máy dev Windows: `{"type":"stdio","command":"cmd","args":["/c","npx","-y","@playwright/mcp@latest","--headless"]}` (npx là script `.cmd`, phải gọi qua `cmd /c`). Trên Linux/CI/máy GPU không có `cmd`, không sửa file này (nó được commit cho máy dev) — thêm server ở **user scope** của máy đó:
```
claude mcp add playwright -- npx -y @playwright/mcp@latest --headless
```
GitHub dùng `gh` CLI (`winget install GitHub.cli`; allow `Bash(gh *)`), không dùng MCP github (đã ngừng hỗ trợ). Postgres chỉ đọc cho data-engineer: ghi BACKLOG, chưa bật.

## Plugin `ctcv-kit` (`plugins/ctcv-kit/`, prompt.md §9.10)
Sinh bằng `make plugin` (= `uv run python scripts/sync_plugin.py`): copy `agents/` (bỏ `hooks`, `mcpServers`, `permissionMode` khỏi frontmatter vì plugin không nhận ba trường này), `skills/`, `hooks/` (+ `hooks.json` chuyển từ `settings.json`, lệnh đổi sang `${CLAUDE_PLUGIN_ROOT}/hooks/run.sh`), `.mcp.json`, `README.md`. Kiểm: `claude plugin validate plugins/ctcv-kit`; `uv run python scripts/sync_plugin.py --check` báo lệch (test hook có kiểm). Không sửa tay trong `plugins/`.

## Kiểm tra
```
python -m json.tool .claude/settings.json       # JSON hợp lệ
uv run pytest .claude/hooks/tests -q            # hook + frontmatter agent/skill + settings + CLAUDE.md ≤ 150 dòng
uv run ruff check .claude/hooks && uv run ruff format --check .claude/hooks
claude plugin validate plugins/ctcv-kit
```
