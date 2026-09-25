# Cầm Tay Chỉ Việc — Bộ prompt và cấu hình Claude Code (Fable 5.1)

2026-09-17 · @Someone

## 1. Cách dùng bộ prompt và thiết lập Claude Code cho Fable 5.1

Bộ prompt này có 3 tầng: **cấu hình repo** (CLAUDE.md, subagent, skill, hook, settings — "bộ não cố định" Claude Code tự đọc mỗi phiên), **prompt điều phối** (prompt tổng và prompt theo lĩnh vực — "lệnh"), và **prompt quy trình** (ngày, review, sửa lỗi — "nhịp"). Bạn cài tầng 1 một lần ở ngày 0, rồi chỉ gõ tầng 2–3. Mọi định dạng dưới đây được đối chiếu với tài liệu chính thức của Claude Code ngày 17/9/2026 ([subagents](https://code.claude.com/docs/en/sub-agents), [model và effort](https://code.claude.com/docs/en/model-config), [hooks](https://code.claude.com/docs/en/hooks), [skills](https://code.claude.com/docs/en/skills), [agent teams](https://code.claude.com/docs/en/agent-teams)).

**Thiết lập phiên để khai thác tối đa Fable 5.1:**

| Thiết lập | Cách làm | Khi nào |
| --- | --- | --- |
| Chọn model | `/model` → Fable, hoặc khởi động `claude --model claude-fable-5-1`; subagent dùng alias `model: fable` | Mọi phiên |
| Effort | `/effort xhigh` cho phiên viết mã hằng ngày; `claude --effort max` cho phiên kiến trúc, gỡ lỗi khó (max chỉ tồn tại theo phiên trừ khi đặt `CLAUDE_CODE_EFFORT_LEVEL`); Fable 5.1 hỗ trợ đủ 5 mức low/medium/high/xhigh/max | Theo loại việc |
| Ultracode | `/effort ultracode` = xhigh + Claude tự dàn dựng dynamic workflow (lập kế hoạch → bạn duyệt → fan-out subagent song song → kiểm chứng → hợp nhất); đây là thiết lập của Claude Code, không phải mức effort của model, và chỉ áp dụng cho phiên hiện tại | Epic lớn nhiều mô-đun độc lập (E02, E10, E11), hackathon |
| Plan mode | Shift+Tab để vào plan mode trước mỗi epic; Claude chỉ đọc và lập kế hoạch, bạn duyệt rồi mới cho sửa | Đầu mỗi epic |
| Quyền | `.claude/settings.json`: `permissions.allow` cho `Bash(make *)`, `Bash(pnpm *)`, `Bash(uv *)`, `Bash(docker compose *)`; `permissions.deny` cho `Bash(git push --force*)`, `Bash(rm -rf *)`, `Read(.env)`, `Read(**/*.pem)`; mode `acceptEdits` cho phiên làm việc | Ngày 0 |
| Subagent | Định nghĩa trong `.claude/agents/*.md`; model mặc định cho subagent bằng `CLAUDE_CODE_SUBAGENT_MODEL=fable` trong `env` của settings; giới hạn đồng thời 20 và độ sâu lồng 3 là mặc định | Ngày 0 |
| Song song | Subagent có `isolation: worktree` để mỗi epic độc lập chạy trên worktree riêng; agent teams (thử nghiệm) bật bằng `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` chỉ khi các nhánh việc cần bàn bạc với nhau | E03∥E04, E08∥E09∥E10 |
| Headless/CI | `claude -p "<prompt>"` trong GitHub Actions cho eval hằng đêm và sửa lỗi CI tự động | Từ E01 |
| Prompt log | Hook `Stop` và `SessionEnd` ghi transcript; không sửa tay | Từ E01 |

**Nguyên tắc dùng effort:** bắt đầu ở xhigh (khuyến nghị chính thức cho công việc agentic và viết mã), nâng lên max chỉ khi eval cho thấy còn dư địa hoặc gặp lỗi khó; hạ về high/medium cho việc lặp lại (sinh dữ liệu, sửa lint) để tiết kiệm.

**Trình tự ngày 0 (30 phút):** cài Claude Code → mở repo có `docs/idea.md`, `docs/plan.md` → chép thư mục `.claude/` và `.mcp.json` từ Phụ lục mục 9 → `claude --model claude-fable-5-1 --effort max` → chạy Prompt tổng (mục 4) trong plan mode → duyệt kế hoạch → thoát plan mode và cho chạy.

**Cách gọi subagent:** để Claude tự chọn theo `description`, hoặc ép bằng `@agent-<tên>` hay câu "Use the qa-tester subagent to …"; kết quả chỉ trả về bản tóm tắt nên ngữ cảnh chính luôn gọn. Việc song song không cần trao đổi qua lại → subagent với worktree; việc cần tranh luận (kiến trúc, review chéo) → agent teams.

## 2. Đội ngũ agent

Một phiên chính (orchestrator) trên Fable 5.1 giữ toàn bộ ngữ cảnh sản phẩm và chỉ điều phối; 10 subagent chuyên môn làm việc trong ngữ cảnh riêng, trả về tóm tắt; subagent chỉ-đọc (kiến trúc, review, red-team) không bao giờ có quyền sửa mã, nên chất lượng được kiểm tra bởi "người" khác với "người" viết.

| Subagent | Vai trò | Tools | Model / effort | Đặc biệt |
| --- | --- | --- | --- | --- |
| `architect` | Đọc idea/plan, lập thiết kế, ADR, chia việc; không sửa mã | Read, Grep, Glob, WebFetch | fable / max | `permissionMode: plan`, `memory: project` |
| `backend-dev` | FastAPI, agent service, tool schema, migration | Read, Edit, Write, Bash, Grep, Glob | fable / xhigh | `isolation: worktree`, `skills: [ctcv-conventions, fastapi-conventions]` |
| `frontend-dev` | PWA React, thiết kế cho người cao tuổi, sandbox UI | Read, Edit, Write, Bash, Grep, Glob | fable / xhigh | `isolation: worktree`, `skills: [ctcv-conventions, elder-ui]`, mcp `playwright` |
| `data-engineer` | Crawler, chuẩn hóa, sinh dữ liệu, registry | Read, Edit, Write, Bash, Grep, Glob, WebFetch | fable / high | `skills: [data-pipeline]`, ngân sách API trong hook |
| `ml-trainer` | LoRA SFT/DPO, lượng tử hóa, YOLOX, model card | Read, Edit, Write, Bash | fable / xhigh | `skills: [training-runbook]`, hook chặn job > 20 giờ GPU |
| `qa-tester` | Viết và chạy test, e2e Playwright, báo cáo lỗi | Read, Edit, Write, Bash, Grep, Glob | fable / high | `skills: [test-strategy]`, mcp `playwright`, `background: true` |
| `security-redteam` | Prompt injection, PII, guardrail, OWASP Agentic | Read, Grep, Glob, Bash | fable / max | Chỉ đọc + chạy `make redteam`; `memory: project` |
| `devops` | Docker, CI, deploy, monitoring, backup, failover | Read, Edit, Write, Bash | fable / high | `disallowedTools: Read(.env)` qua permissions.deny |
| `reviewer` | Review PR theo DoD và checklist bảo mật | Read, Grep, Glob, Bash | fable / xhigh | Chỉ đọc; `memory: project` lưu mẫu lỗi lặp |
| `docs-writer` | README, ADR, CHANGELOG, hồ sơ BTC, script video | Read, Edit, Write, Bash | fable / high | `skills: [dossier-btc]` |

**Luồng điều phối chuẩn cho một epic:**

```mermaid
flowchart LR
  O[Orchestrator<br/>Fable xhigh] --> A[architect<br/>thiết kế + chia việc]
  A --> O
  O --> B[backend-dev<br/>worktree]
  O --> F[frontend-dev<br/>worktree]
  O --> D[data-engineer]
  B --> Q[qa-tester]
  F --> Q
  D --> Q
  Q --> R[reviewer]
  R --> S[security-redteam]
  S --> O
  O --> W[docs-writer]
```

Orchestrator không tự viết mã lớn; nó giao việc, đọc tóm tắt, hợp nhất worktree, và chỉ tự sửa những thay đổi nhỏ dưới 30 dòng.

**Quy tắc điều phối (ghi trong CLAUDE.md, mục "Delegation"):**

1. Trước khi sửa mã ở epic mới: gọi `architect` lập thiết kế và danh sách việc có tiêu chí xong; orchestrator chỉ tiếp tục khi có kế hoạch.
2. Việc độc lập (backend/frontend/data) chạy song song trên worktree; orchestrator hợp nhất theo thứ tự backend → frontend → data, chạy `make check` sau mỗi lần hợp nhất.
3. Mọi thay đổi mã phải qua `qa-tester` (test xanh) rồi `reviewer` (DoD) trước khi báo bạn; sửa guardrail hoặc tool của agent phải thêm `security-redteam`.
4. Subagent trả về tối đa 40 dòng tóm tắt + đường dẫn file; log dài để trong file, không đưa vào ngữ cảnh chính.
5. Không lồng quá 2 tầng subagent; không quá 6 subagent chạy đồng thời để giữ chi phí và tránh xung đột worktree.
6. Khi hai subagent bất đồng (ví dụ reviewer vs backend-dev), orchestrator mở agent team 2 thành viên để tranh luận có giới hạn 10 phút rồi quyết, ghi ADR.

**Khi nào dùng agent teams thay subagent:** review kiến trúc đa góc nhìn ở E01 và E05, điều tra sự cố ở giai đoạn đóng băng, và ngày hackathon khi 3 thành viên người thật cũng chia theo mô-đun; ngoài các trường hợp này, subagent rẻ hơn và đủ.

## 3. Cấu hình repo cho Claude Code

Toàn bộ cấu hình nằm trong `.claude/` và `.mcp.json` ở gốc repo, được commit để cả đội và CI dùng chung; file mẫu đầy đủ ở mục 9.

```
.claude/
  settings.json            # quyền, env, hooks, model mặc định cho subagent
  settings.local.json      # bí mật/đường dẫn máy cá nhân (không commit)
  agents/                  # 10 subagent ở mục 2 (mỗi file .md có frontmatter)
  skills/
    ctcv-conventions/SKILL.md   # quy ước mã, cấu trúc, DoD (Claude tự nạp khi liên quan)
    fastapi-conventions/SKILL.md
    elder-ui/SKILL.md           # thiết kế cho người cao tuổi, token thiết kế, kiểm tra a11y
    coach-style/SKILL.md        # phong cách huấn luyện viên tiếng Việt, prompt mẫu, ràng buộc
    data-pipeline/SKILL.md      # make data, schema registry, lọc, LLM-judge
    training-runbook/SKILL.md   # LoRA/DPO/quantize/YOLOX, ngưỡng, model card
    test-strategy/SKILL.md      # kim tự tháp test, e2e, fixtures, seed
    agent-security/SKILL.md     # CaMeL, OWASP Agentic, red-team, PII
    dossier-btc/SKILL.md        # sinh hồ sơ 20 trang, video, kê khai (chỉ gọi tay: /dossier)
    hackathon-kit/SKILL.md      # quy trình 2 ngày và 12 giờ (chỉ gọi tay: /hackathon)
    epic/SKILL.md               # /epic E0X → chạy vòng lặp epic chuẩn
    daily/SKILL.md              # /daily → cập nhật DAILY.md và rà tiến độ
  hooks/                   # script shell cho hook (guard.sh, format.sh, promptlog.sh, budget.sh)
.mcp.json                  # playwright (e2e/ảnh màn hình), github (PR/issue), postgres (chỉ đọc)
.claude-plugin/plugin.json # đóng gói toàn bộ thành plugin "ctcv-kit" để tái dùng cho hackathon
```

**Skill vs subagent vs hook — dùng đúng chỗ:** skill là kiến thức và quy trình tái dùng chạy trong ngữ cảnh hiện tại (hoặc `context: fork` để tách); subagent là "người" có ngữ cảnh, tool và model riêng; hook là luật cứng chạy bằng shell, mô hình không thể bỏ qua. Luật an toàn (không đọc `.env`, không `rm -rf`, không vượt ngân sách GPU) phải là hook, không phải lời dặn trong prompt.

**Hook (trong `settings.json`, kèm script ở `.claude/hooks/`):**

| Sự kiện | Matcher | Script | Tác dụng |
| --- | --- | --- | --- |
| SessionStart | – | `session-start.sh` | In `docs/status/DAILY.md`, epic hiện tại, kết quả `make check` gần nhất vào ngữ cảnh |
| UserPromptSubmit | – | `prompt-guard.sh` | Ghi prompt vào log; chặn prompt chứa bí mật (token, khóa) |
| PreToolUse | `Bash` | `guard.sh` | Exit 2 nếu lệnh nguy hiểm (`rm -rf`, `git push --force`, `docker system prune`), nếu đọc `.env`, hoặc nếu job train vượt ngân sách (`budget.sh` đọc `training/budget.json`) |
| PreToolUse | `Edit\|Write` | `protect-paths.sh` | Chặn sửa `docs/prompt-log/**`, `data/registry/*.lock`, file migration đã merge |
| PostToolUse | `Edit\|Write` | `format.sh` | Chạy ruff/prettier trên file vừa sửa; chạy test nhanh của mô-đun; trả lỗi về Claude |
| PostToolUseFailure | `Bash` | `notify.sh` | Ghi lỗi vào `docs/status/errors.log` để orchestrator tổng hợp |
| SubagentStop | – | `subagent-log.sh` | Lưu tóm tắt subagent kèm thời gian và tên vào log |
| Stop | – | `promptlog.sh` + `daily.sh` | Ghi transcript phiên (hash SHA-256), cập nhật DAILY.md, nhắc checklist PR |
| PreCompact | – | `checkpoint.sh` | Ghi trạng thái việc đang làm vào `docs/status/CHECKPOINT.md` trước khi nén ngữ cảnh |
| SessionEnd | – | `promptlog.sh` | Đóng log phiên, cập nhật INDEX |

Hook loại `agent` (Claude Code hỗ trợ `type: agent` với prompt kiểm chứng) dùng cho cổng `Stop` của epic: "Xác nhận make check xanh và PR có checklist" — nếu chưa, hook chặn kết thúc và yêu cầu tiếp tục.

**MCP (`.mcp.json`):** `playwright` để subagent frontend/qa chụp ảnh và chạy e2e thật; `github` để tạo PR, đọc review; `postgres` chỉ đọc cho `data-engineer` kiểm tra dữ liệu. Mọi MCP khác bị từ chối qua `permissions.deny: ["mcp__*"]` ngoài danh sách.

**Plugin `ctcv-kit`:** đóng gói agents, skills, hooks, `.mcp.json` vào `.claude-plugin/plugin.json` (name, version, description) và kiểm tra bằng `claude plugin validate .`; ngày hackathon chỉ cần cài plugin vào repo mới là có toàn bộ đội ngũ và quy trình trong 5 phút. Lưu ý: subagent trong plugin không nhận `hooks`, `mcpServers`, `permissionMode` — các trường này phải nằm ở `.claude/agents/` của repo đích hoặc `settings.json`.

## 4. Prompt tổng (Master Prompt) — chạy một lần ở ngày 1

Dán nguyên văn vào Claude Code (đã ở chế độ `--model claude-fable-5-1 --effort max`, plan mode bật) trong repo đã có `docs/idea.md`, `docs/plan.md`, `.claude/`, `.mcp.json`; prompt này tạo ra bộ khung mà 20 ngày còn lại chỉ việc chạy `/epic`.

```text
Bạn là kỹ sư trưởng kiêm điều phối viên (orchestrator) của dự án "Cầm Tay Chỉ Việc" (CTCV) — trợ lý AI đồng hành phong trào Bình dân học vụ số, dự thi Bảng C cuộc thi Sáng tạo trẻ Quốc gia về AI 2026. Mục tiêu tối thượng: một sản phẩm chạy thật, an toàn, đo được, và bộ hồ sơ đầy đủ theo yêu cầu Ban Tổ chức; chất lượng ở mức sản phẩm thương mại, không phải bản demo.

NGUỒN SỰ THẬT
- docs/idea.md (sản phẩm, người dùng, mô hình, dữ liệu, đánh giá, đạo đức) và docs/plan.md (phạm vi, kiến trúc, API, schema, 12 epic, runbook, cổng chất lượng, prompt). Đọc trọn vẹn cả hai trước khi làm gì. Mâu thuẫn: plan.md thắng về quy trình, idea.md thắng về sản phẩm; nếu vẫn mơ hồ, hỏi tôi tối đa 3 câu.
- CLAUDE.md, .claude/agents, .claude/skills, hooks là ràng buộc vận hành; không sửa chúng nếu chưa có ADR được tôi duyệt.

BA NGUYÊN TẮC BẤT BIẾN (phải có test bảo vệ)
1. Agent sản phẩm không có tool nào tác động lên hệ thống thật hoặc tài khoản thật; sandbox là hệ thống giả lập tách biệt.
2. Không lưu dữ liệu định danh (CCCD, số tài khoản, OTP, mật khẩu); ảnh màn hình che PII và xóa sau 60 giây.
3. Mọi dữ kiện nói với người dân phải có trích dẫn nguồn chính thống; không có nguồn thì nói "không chắc" và chuyển tình nguyện viên.

NHIỆM VỤ PHIÊN NÀY (E01 — trong plan mode, trình kế hoạch trước, chỉ thực thi sau khi tôi duyệt)
A. Gọi subagent `architect` để: (1) xác nhận kiến trúc và ranh giới 6 dịch vụ theo plan.md mục 5; (2) chốt cấu trúc thư mục monorepo theo idea.md 15.1; (3) chốt cấu trúc dữ liệu: schema PostgreSQL 9 bảng, schema JSON kịch bản sandbox (idea.md 15.2), schema kịch bản lừa đảo (plan.md mục 15), registry datasets.yaml/models.yaml, contract API 14 endpoint; (4) chia 12 epic thành danh sách việc có tiêu chí xong; (5) viết ADR-001 (kiến trúc, stack), ADR-002 (chọn model: Qwen3.5-9B planner, Qwen3-VL-8B, PhoWhisper, TTS mã nguồn mở, BGE-m3, YOLOX Apache-2.0), ADR-003 (sandbox thay vì thao tác hệ thống thật), ADR-004 (tách planner/quarantined LLM), ADR-005 (chính sách dữ liệu, TTL ảnh).
B. Dựng khung: monorepo (apps/web, apps/android, services/api, services/agent, services/speech, services/vision, sandbox, data, training, eval, deploy, docs), Docker Compose đủ dịch vụ, Makefile với mọi target ở plan.md mục 15, pre-commit (ruff, eslint, prettier, gitleaks), GitHub Actions chạy make check trên PR, mẫu PR, CHANGELOG, LICENSE Apache-2.0, SECURITY.md, README chạy 1 lệnh.
C. Sinh 12 file epics/E01..E12.md theo bảng plan.md mục 6 và mẫu mục 14 (Phụ lục B): mục tiêu, đầu vào, công việc, đầu ra, test nghiệm thu chạy được, không được làm, câu hỏi mở ≤ 3, checklist ≤ 30 phút cho tôi.
D. Thiết lập chất lượng từ dòng đầu: cấu trúc test (unit/integration/e2e), fixtures và seed cố định, coverage gate 80% cho services/agent, sandbox, services/api; eval harness rỗng có ngưỡng từ plan.md mục 7; make redteam với 50 kịch bản khởi đầu; make doctor kiểm tra môi trường.
E. Chạy make doctor và make check đến khi xanh; gọi `reviewer` review toàn bộ khung theo DoD; gọi `security-redteam` kiểm tra hook/permissions; mở PR "[E01] Khung repo".

CHUẨN CHẤT LƯỢNG ÁP DỤNG TỪ E01
- Test trước, mã sau; không xóa hay bỏ qua test để cho xanh; coverage không giảm.
- Hàm ≤ 50 dòng, docstring tiếng Anh, thông điệp lỗi cho người dùng bằng tiếng Việt đời thường; không hard-code URL/model/ngưỡng — mọi thứ trong config/*.yaml có test schema.
- Mọi tool của agent có schema Pydantic, whitelist, test riêng; mọi prompt hệ thống ở config/prompts/ có phiên bản.
- Giao diện: cỡ chữ ≥ 20 pt, một hành động mỗi màn hình, giọng nói là kênh mặc định, có nút "Nói lại" và "Gọi tình nguyện viên"; kiểm tra tự động bằng test CSS và Playwright trên 3 viewport.
- Tài liệu đi cùng mã: README mô-đun, ADR cho quyết định lớn, DAILY.md sau mỗi phiên, prompt log tự động (không sửa tay).

CÁCH LÀM VIỆC
- Bạn điều phối, subagent làm: architect (thiết kế), backend-dev/frontend-dev/data-engineer (thực thi song song trên worktree), ml-trainer, qa-tester (test), reviewer và security-redteam (kiểm tra độc lập), devops (deploy), docs-writer (tài liệu). Bạn chỉ tự sửa thay đổi nhỏ dưới 30 dòng.
- Subagent trả về ≤ 40 dòng tóm tắt + đường dẫn file. Không quá 6 subagent đồng thời, không lồng quá 2 tầng.
- Tối đa 3 vòng tự sửa cho một lỗi; quá 3 vòng, báo tôi kèm log và 2 hướng xử lý.
- Dừng và hỏi tôi khi: đổi schema DB sau E05, thêm tool cho agent, đổi model, chạm dữ liệu người dùng thật, tác vụ vượt 20 giờ GPU hoặc 500.000 đồng API, thêm thư viện ngoài danh sách trong CLAUDE.md.
- Không mở rộng phạm vi ngoài plan.md mục 2; đề xuất cải tiến ghi vào docs/decisions/BACKLOG.md thay vì tự làm.

ĐẦU RA CỦA PHIÊN
1. Kế hoạch E01 trong plan mode (≤ 40 dòng) để tôi duyệt.
2. Sau khi duyệt: PR E01 với make check xanh, 5 ADR, 12 epic, báo cáo reviewer và security-redteam.
3. Tóm tắt cuối ≤ 15 dòng: đã làm gì, test gì, tôi cần kiểm tra gì trong 30 phút, rủi ro nào cần quyết.
```

**Sau prompt tổng, mỗi ngày bạn chỉ dùng 2 lệnh:** `/daily` (mục 6) và `/epic E0X` (skill ở mục 9 gói toàn bộ vòng lặp epic: đọc epic → architect → thực thi song song → qa → reviewer → security → PR). Prompt theo lĩnh vực ở mục 5 dùng khi bạn muốn can thiệp sâu vào một mảng.

## 5. Prompt theo lĩnh vực

Sáu prompt này gọi đúng subagent chuyên môn và nêu tiêu chí xong đo được; dùng khi bạn muốn đẩy sâu một mảng (ví dụ làm lại UI) mà không chạy lại cả epic. Mỗi prompt tự tham chiếu idea/plan nên ngắn.

**D1 — Dữ liệu và huấn luyện (E03, E06, E07, E08):**

```text
Giao cho `data-engineer` và `ml-trainer`, chạy song song ở chỗ độc lập. Yêu cầu:
1. data-engineer: hiện thực đầy đủ pipeline make data theo plan.md mục 7 (crawl robots-aware 1 req/s, chuẩn hóa, chunk theo bước hướng dẫn, Qdrant hybrid, sinh kịch bản JSON + validator, render 20.000 ảnh với nhãn từ DOM ở 6 viewport, sinh 8.000 hội thoại SFT + 2.000 cặp DPO qua bộ lọc ràng buộc và LLM-judge ≥ 4/5, 20 kịch bản lừa đảo ở mức mẫu hành vi, tập đánh giá seed cố định, registry có sha256 và giấy phép). Đầu ra: báo cáo HTML 30 mẫu gắn cờ cho tôi duyệt; recall@5 ≥ 0,9 trên 100 câu hỏi có nhãn.
2. ml-trainer: LoRA SFT (r=16, 3 epoch) → DPO (beta 0,1) → AWQ 4-bit và GGUF Q4_K_M cho bản 1.7B → YOLOX-Tiny 50 epoch → model card; mỗi run trong training/runs/ có config, log, metrics; bảng ablation training/reports/ablation.md so sánh base / SFT / SFT+DPO / có-không xác nhận ý định / có-không trích dẫn / VLM đơn vs YOLOX+VLM / 9B vs 1.7B.
Ràng buộc: dừng hỏi tôi nếu một bước dự kiến > 20 giờ GPU hoặc > 500.000 đồng API; không đổi model đang phục vụ nếu eval dưới ngưỡng chặn; mọi số liệu ghi vào eval/reports. Kết thúc: qa-tester chạy make eval đầy đủ, reviewer xác nhận registry và model card khớp thực tế.
```

**D2 — Backend và agent (E02, E05, E10):**

```text
Giao cho `backend-dev` (worktree riêng), sau đó `security-redteam` và `reviewer`. Yêu cầu:
- Hiện thực đúng contract API 14 endpoint và schema 9 bảng ở plan.md mục 5 (Alembic migration có test); SSE cho /sessions/{id}/events.
- services/agent: planner (Qwen3.5-9B qua vLLM, đầu ra JSON {say, action_hint, tool_calls, confidence}), quarantined LLM cho văn bản không tin cậy, tool router chỉ nhận 8 tool có schema Pydantic, guardrail cứng (từ chối OTP/mật khẩu/số thẻ; từ chối hành động trên hệ thống thật; ≤ 2 câu; xác nhận ý định lượt đầu), verify.py kiểm chứng trích dẫn bằng reranker + judge nhỏ, escalate khi confidence < ngưỡng trong config.
- Sandbox engine: máy trạng thái từ JSON, validator từ chối kịch bản lỗi, log sự kiện vào Redis Stream, worker tổng hợp chỉ số mỗi phút.
Tiêu chí xong: pytest coverage ≥ 80% cho services/agent, sandbox, services/api; 500 hội thoại giữ lại đạt 100% ≤ 2 câu và 100% xác nhận ý định; make redteam = 0; p95 một lượt (không tính ASR/TTS) < 1,2 s trên staging. security-redteam phải thử ít nhất: injection qua nội dung dán, qua ảnh, qua kết quả tool giả, qua câu hỏi nhiều bước; mỗi lỗ hổng tìm thấy → test hồi quy.
```

**D3 — UI/UX và frontend (E02, E04, E08, E10):**

```text
Giao cho `frontend-dev` với skill elder-ui, dùng MCP playwright để tự chụp và kiểm tra. Yêu cầu thiết kế: hệ thống token (cỡ chữ cơ sở 20 pt, tương phản ≥ 7:1, vùng bấm ≥ 56 px, tối đa 1 hành động chính/màn hình, màu có tên gọi được: xanh/đỏ/vàng), giọng nói là kênh mặc định (nút micro to, sóng âm khi nghe, phụ đề chữ to), luôn có "Nói lại" và "Gọi tình nguyện viên", không thuật ngữ, thông điệp lỗi kiểu khích lệ. Sandbox 12 kịch bản dựng theo bố cục ứng dụng thật nhưng nhãn "Ứng dụng mô phỏng", dữ liệu giả; highlight bước tiếp theo bằng khung động; kèm cặp tại chỗ vẽ khung lên ảnh. Dashboard tình nguyện viên ưu tiên bảng tiến độ và "3 người cần kèm hôm nay". PWA cài được, offline cho màn hình tĩnh.
Tiêu chí xong: Playwright e2e 12 kịch bản xanh trên 3 viewport (360×800, 390×844, 412×915); test CSS cỡ chữ và vùng bấm; kiểm tra a11y tự động (axe) 0 lỗi nghiêm trọng; ảnh chụp mọi màn hình đưa vào docs/screens/ để tôi duyệt; Lighthouse mobile ≥ 90 hiệu năng và a11y. Trước khi code, frontend-dev nộp cho tôi 3 phương án bố cục màn hình chính dưới dạng ảnh chụp mock (HTML thật, không mô tả chữ) để chọn.
```

**D4 — Deploy và vận hành (E11, E12):**

```text
Giao cho `devops`, `qa-tester` (load test) và `security-redteam` (kiểm tra bề mặt tấn công). Yêu cầu: docker compose cho dev/staging/prod; Caddy HTTPS; Cloudflare trước máy; vLLM phục vụ Qwen3.5-9B AWQ và Qwen3-VL-8B trên 1 GPU 24 GB với VLM tải theo yêu cầu; faster-whisper INT8; TTS cache; Uptime Kuma + Prometheus + Grafana + cảnh báo Telegram (p95 > 3 s/5 phút, lỗi > 2%, VRAM > 92%, dịch vụ down 2 lần); backup PostgreSQL 6 giờ, Qdrant hằng ngày, make restore-drill; make deploy/rollback/failover; status page công khai; APK offline (GGUF 1.7B + PhoWhisper-tiny + YOLOX ONNX) chạy 6 kịch bản khi tắt mạng.
Tiêu chí xong: deploy từ tag bằng CI; smoke test 12 kịch bản; load test 50 người đồng thời p95 < 2,5 s, lỗi < 1%; uptime 24 giờ liên tục trên staging trước khi lên prod; gitleaks, pip-audit, npm audit sạch; kịch bản failover diễn tập thành công dưới 5 phút; tài liệu vận hành docs/ops/RUNBOOK.md.
```

**D5 — Đánh giá và red-team (mọi epic, nặng ở E05, E07, E11):**

```text
Giao cho `qa-tester` (harness) và `security-redteam` (tấn công), độc lập với người viết mã. Yêu cầu harness: make eval [--quick] chạy 6 bộ ở plan.md mục 7 với seed cố định, xuất Markdown + PNG, so ngưỡng chấp nhận và ngưỡng chặn; LLM-judge có bộ 100 mẫu người kiểm để hiệu chỉnh; báo cáo ablation tự sinh. Yêu cầu red-team: 200 kịch bản gồm prompt injection trực tiếp và gián tiếp (qua nội dung dán, ảnh, kết quả tool), moi OTP/mật khẩu, yêu cầu thao tác thay người dùng, rò rỉ prompt hệ thống, PII trong log, lạm dụng kịch bản lừa đảo; mỗi kịch bản có expected và bộ chấm tự động; chạy trong CI và trước mỗi tag.
Tiêu chí xong: 0 rò rỉ; mọi lỗ hổng đã sửa có test hồi quy; báo cáo eval và red-team nhúng được vào hồ sơ; danh sách "kết quả chưa đạt" ghi trung thực.
```

**D6 — Sản phẩm và hồ sơ (D17–D21):**

```text
Giao cho `docs-writer` với skill dossier-btc, `qa-tester` kiểm tra số liệu. Yêu cầu: make pilot-kit (phiếu đồng thuận chữ to, checklist buổi, ứng dụng bấm giờ nhóm đối chứng, mẫu ghi chú); make pilot-report từ log (bảng trước/sau, khoảng tin cậy bootstrap, biểu đồ); make dossier sinh 7 file theo plan.md mục 10 (PDF ≤ 20 trang điền vào mẫu BTC, slide + script 5 phút, kịch bản Playwright video demo 5 phút, kê khai AI từ registry và lockfile, prompt log ZIP có hash, README/LICENSE/SECURITY). Mọi số phải truy vết được về eval/reports hoặc eval/pilot/report.md; mục "kết quả chưa đạt" bắt buộc; ảnh màn hình là ảnh thật bản v1.0.
Tiêu chí xong: script so khớp số liệu PDF ↔ báo cáo eval = 0 sai lệch; đếm trang ≤ 20; video ≤ 300 s; reviewer đọc PDF như giám khảo và liệt kê 10 câu hỏi phản biện kèm câu trả lời chuẩn bị.
```

## 6. Prompt quy trình

Các prompt này được gói thành skill gọi bằng dấu `/` (mục 9) để bạn không phải gõ lại; dưới đây là nội dung để bạn hiểu và chỉnh.

| Lệnh | Khi dùng | Nội dung cốt lõi |
| --- | --- | --- |
| `/daily` | Đầu mỗi ngày | Cập nhật `docs/status/DAILY.md` (epic, % test xanh, eval quick, red-team, p95, chi phí, câu hỏi chờ, rủi ro); so với plan.md mục 6; nếu D10 hoặc D17 → báo cáo rà phạm vi và đề xuất cắt |
| `/epic E0X` | Mỗi epic | Vòng lặp chuẩn: plan mode → architect → thực thi song song trên worktree → qa-tester → reviewer → security-redteam (nếu chạm agent/guardrail) → PR có checklist ≤ 30 phút; không chuyển epic khi PR chưa merge |
| `/review E0X` | Sau khi bạn test | Đọc bình luận PR; với mỗi góp ý: xác nhận hiểu, sửa, test hồi quy; tự review lại theo DoD; bảng góp ý → thay đổi → test |
| `/fix` | Khi CI đỏ hoặc lỗi runtime | `debugger`-style: tái hiện, cô lập, sửa tối thiểu, test hồi quy, giải thích nguyên nhân gốc; tối đa 3 vòng rồi báo |
| `/refactor <đường dẫn>` | Khi mô-đun phình | Chỉ khi có test bao phủ; giữ hành vi, giảm phức tạp, không đổi API công khai; đo trước/sau (dòng, cyclomatic) |
| `/incident` | Sự cố khi vận hành/đóng băng | Thu thập log/metrics, xác định phạm vi, áp runbook plan.md mục 8, ghi `docs/ops/incidents.md`, đề xuất phòng ngừa |
| `/hackathon` | Vòng khu vực và chung kết | Đọc `hackathon/input/`, đề xuất 2 bài toán con, lịch giờ, dùng plugin ctcv-kit, cập nhật DAILY mỗi 4 giờ |

**Prompt `/review` (nguyên văn trong skill):**

```text
Tôi đã test PR $ARGUMENTS; góp ý nằm trong bình luận PR (đọc bằng MCP github). Với mỗi góp ý: (1) diễn đạt lại để xác nhận hiểu đúng, (2) sửa, (3) thêm test hồi quy, (4) chạy make check. Sau đó gọi `reviewer` review lại toàn bộ PR theo Definition of Done (plan.md mục 14) và checklist bảo mật trong CLAUDE.md; gọi `security-redteam` nếu PR chạm services/agent, guardrail, tool, hook hoặc permissions. Kết thúc bằng bảng: góp ý → thay đổi → test; liệt kê điểm bạn tự phát hiện thêm.
```

**Prompt `/fix` (nguyên văn):**

```text
Lỗi: $ARGUMENTS (hoặc lấy từ CI/log mới nhất). Quy trình: tái hiện bằng test thất bại → cô lập vị trí bằng subagent chỉ đọc nếu cần đọc nhiều file → sửa tối thiểu ở nguyên nhân gốc, không sửa triệu chứng → test hồi quy → make check. Tối đa 3 vòng; nếu chưa xong, báo tôi kèm log 30 dòng cuối, giả thuyết còn lại và 2 hướng xử lý. Không xóa/bỏ qua test, không nới ngưỡng eval, không đổi cấu hình bảo mật để cho xanh.
```

**Prompt `/hackathon` (nguyên văn):**

```text
Đề và dataset ở hackathon/input/. Giờ 0–2: `architect` đọc đề, khám phá dữ liệu (subagent chỉ đọc), đề xuất 2 bài toán con chứng minh được bằng số, kèm kế hoạch giờ theo idea.md mục 13; tôi chọn. Giờ 2–6: dựng ingestion + RAG có trích dẫn + eval baseline bằng plugin ctcv-kit. Giờ 6–14: tính năng lõi (backend-dev ∥ frontend-dev ∥ data-engineer). Giờ 14–20: qa + red-team + deploy staging. Giờ 20–34: dữ liệu thật, kết quả, ablation. Giờ 34–40: docs-writer làm slide, script demo; qa chạy lại. Giờ 40–48: dự phòng. Mỗi 4 giờ chạy /daily. Giữ ba nguyên tắc bất biến. Cho thử thách 12 giờ: ưu tiên tối ưu độ trễ (batching vLLM, cache TTS, lượng tử hóa) → bảo mật (mở rộng red-team, báo cáo trước/sau) → tích hợp tool/nguồn mới cho agent (< 1 giờ mỗi tool nhờ schema có sẵn).
```

**Nhịp một ngày điển hình:** `/daily` (5 phút) → `/epic E0X` (Claude làm 2–5 giờ, bạn làm việc khác; hook `Stop` nhắc khi xong) → bạn test 30 phút theo checklist trong PR → `/review E0X` → merge, tag. Ngày có huấn luyện: chạy D1 buổi tối, sáng hôm sau đọc báo cáo.

## 7. Kiểm thử và đánh giá

Kiểm thử được tách khỏi người viết mã (qa-tester và reviewer là subagent riêng, chỉ đọc hoặc chỉ sửa test), chạy ở 4 tầng từ commit đến phát hành, và có một tầng riêng cho chất lượng AI (eval, red-team) vì test xanh không có nghĩa là huấn luyện viên nói đúng.

| Tầng | Loại | Công cụ | Ai viết | Ngưỡng |
| --- | --- | --- | --- | --- |
| 1. Đơn vị | Hàm, tool, guardrail, máy trạng thái, schema | pytest, vitest | backend-dev/frontend-dev viết trước khi code; qa-tester bổ sung | Coverage ≥ 80% mô-đun lõi |
| 2. Tích hợp | API ↔ DB ↔ Redis ↔ Qdrant ↔ vLLM (mock có ghi) | pytest + testcontainers | qa-tester | Mọi endpoint có test hợp đồng (schema request/response) |
| 3. E2E | 12 kịch bản sandbox bằng giọng nói giả lập trên 3 viewport; dashboard; kèm cặp | Playwright (MCP) | qa-tester | 100% kịch bản đã ship; ảnh chụp lưu docs/screens |
| 4. Phi chức năng | Tải, độ trễ, a11y, Lighthouse, restore-drill | k6/Locust, axe, Lighthouse | qa-tester + devops | p95 < 2,5 s; a11y 0 lỗi nghiêm trọng; Lighthouse ≥ 90 |
| 5. Chất lượng AI | Q&A trích dẫn, hội thoại, ảnh, audio, ablation | make eval (harness riêng) | qa-tester + ml-trainer | Ngưỡng plan.md mục 7 |
| 6. An toàn | 200 kịch bản red-team, PII, prompt injection | make redteam | security-redteam | 0 lỗi |

**Quy tắc để test có giá trị thật:**

1. Test viết trước từ tiêu chí nghiệm thu trong epic; một hành vi = một test có tên mô tả bằng tiếng Anh rõ nghĩa.
2. Fixture và seed cố định; dữ liệu test sinh từ pipeline (không chép tay); test không gọi mô hình thật trừ tầng eval — dùng bản ghi (record/replay) cho vLLM để test nhanh và ổn định.
3. Cấm `skip`, `xfail` mới không có ADR; cấm nới ngưỡng eval để xanh; hook `protect-paths.sh` chặn sửa file ngưỡng trong `config/eval.yaml` ngoài PR có nhãn `eval-threshold`.
4. Ba nguyên tắc bất biến có test riêng trong `tests/invariants/`: (a) không tool nào ngoài whitelist; (b) không PII trong log/DB (quét regex trên fixture); (c) câu có dữ kiện phải có citation hợp lệ.
5. Mọi lỗi tìm thấy ở red-team hoặc pilot → test hồi quy trước khi sửa.

**Vòng kiểm thử do subagent tự vận hành:**

```mermaid
flowchart LR
  A[backend/frontend-dev<br/>PR draft] --> B[qa-tester<br/>viết thêm test, chạy make check]
  B -- đỏ --> A
  B -- xanh --> C[reviewer<br/>DoD + đọc diff]
  C -- yêu cầu sửa --> A
  C -- đạt --> D{Chạm agent/guardrail?}
  D -- Có --> E[security-redteam<br/>make redteam + tấn công mới]
  E -- lỗi --> A
  E -- 0 lỗi --> F[Orchestrator<br/>PR sẵn sàng cho bạn]
  D -- Không --> F
```

Bạn chỉ thấy PR khi đã qua cả vòng; checklist ≤ 30 phút trong PR là những gì máy không kiểm được (câu chữ, cảm giác dùng, độ "thật" của mô phỏng).

**Đánh giá AI đúng cách:** tách tập dev/test, không tối ưu trên test; LLM-judge phải được hiệu chỉnh bằng 100 mẫu người chấm (báo cáo độ đồng thuận); báo cáo theo lát cắt (giọng vùng miền, nhóm tuổi, kỹ năng) chứ không chỉ trung bình; ablation cho từng thành phần; ghi rõ "kết quả chưa đạt". Người chấm cuối cùng là 30 người dùng pilot, không phải benchmark.

**Tiêu chí chấp nhận phát hành (`make release-check`):** make check xanh; eval đầy đủ đạt ngưỡng chấp nhận; red-team 0; load test đạt; a11y 0 nghiêm trọng; CHANGELOG có mục; ADR cho thay đổi lớn; prompt log và DAILY cập nhật; reviewer ký.

## 8. Khai thác tối đa mô hình và anti-pattern

Hiệu quả của Fable 5.1 phụ thuộc vào ba thứ bạn kiểm soát được: ngữ cảnh sạch, effort đúng việc, và vòng phản hồi có kiểm chứng; mô hình mạnh nhưng ngữ cảnh đầy rác thì vẫn sai.

**Quản lý ngữ cảnh:**

| Việc | Cách làm |
| --- | --- |
| Giữ CLAUDE.md ngắn | ≤ 150 dòng, chỉ luật và tham chiếu; chi tiết để trong skill (nạp khi cần) |
| Một epic một phiên | `/clear` khi đổi epic; DAILY.md + CHECKPOINT.md là bộ nhớ, không phải lịch sử chat |
| Đẩy việc nặng ra subagent | Đọc nhiều file, chạy test dài, crawl → subagent; ngữ cảnh chính chỉ nhận tóm tắt |
| Nén có kiểm soát | `/compact` ở cuối một việc trọn vẹn, không giữa chừng; hook PreCompact lưu trạng thái |
| Fork khi cần lịch sử | `/subtask` (fork) cho việc phụ cần toàn bộ ngữ cảnh hiện tại, ví dụ soạn test cho thay đổi vừa làm |
| Trí nhớ có chủ đích | `memory: project` cho reviewer, architect, security-redteam để tích lũy mẫu lỗi; yêu cầu "lưu điều đã học" cuối phiên |

**Effort và tư duy sâu:** xhigh cho viết mã hằng ngày; max cho thiết kế kiến trúc (E01), guardrail (E05), gỡ lỗi khó, và rà soát trước nộp; ultracode cho epic nhiều mô-đun độc lập hoặc ngày hackathon (Claude lập workflow, bạn duyệt các pha, fan-out song song, tự kiểm chứng, hợp nhất); medium cho việc lặp lại (sinh dữ liệu, sửa lint); plan mode trước mọi thay đổi ≥ 3 file.

**Vòng phản hồi có kiểm chứng:** mỗi yêu cầu luôn kèm tiêu chí xong đo được (lệnh, ngưỡng, ảnh chụp); yêu cầu bằng chứng (log, ảnh, số) thay vì lời khẳng định; để subagent khác kiểm tra người làm; ép ghi ADR khi đổi hướng để tránh dao động.

**Anti-pattern cần tránh (đã thấy ở nhiều dự án vibe-code):**

1. Dán cả tài liệu vào prompt mỗi lần thay vì để trong repo và tham chiếu → lãng phí ngữ cảnh, dễ lệch phiên bản.
2. Cho phép mọi quyền (`bypassPermissions`) để "cho nhanh" → mất lưới an toàn; dùng `acceptEdits` + allow/deny list + hook.
3. Để một phiên chạy nhiều epic liên tiếp không `/clear` → nén ngữ cảnh làm mất quy ước, lỗi lặp.
4. Chấp nhận "test đã xanh" mà không nhìn diff → mô hình có thể đã nới ngưỡng hoặc skip test; hook và reviewer chặn việc này.
5. Không có nhóm đối chứng và số đo trước/sau ở pilot → hồ sơ chỉ có cảm nhận.
6. Mở rộng phạm vi vì "tiện tay" → ghi BACKLOG.md, không làm.
7. Dùng API thương mại làm lõi sản phẩm rồi ghi "tự làm chủ" → vi phạm kê khai; API chỉ ở bước sinh dữ liệu và được kê khai.
8. Sửa prompt log hoặc commit history để "đẹp" → vi phạm quy định BTC; giữ nguyên, kể cả phiên lỗi.
9. Quá nhiều subagent song song trên cùng file → xung đột; chia theo thư mục và worktree.
10. Bỏ qua người dùng thật vì bận thi khác → lịch pilot đặt từ ngày 1.

**Kiểm soát chi phí:** GPU bật theo lịch (hook `budget.sh` từ chối job khi vượt); subagent chỉ đọc chạy ở effort thấp hơn khi việc đơn giản; eval quick trong CI, eval đầy đủ hằng đêm; cache prompt tự nhiên nhờ CLAUDE.md và skill ổn định (không đổi đầu prompt mỗi phiên).

**Dấu hiệu bạn đang dùng đúng:** mỗi ngày merge ≥ 1 PR có checklist đã tick; DAILY.md kể được câu chuyện tiến độ; số câu hỏi Claude hỏi bạn giảm dần theo ngày; red-team và eval không cần bạn nhắc; bạn dành thời gian cho người dùng và hồ sơ thay vì sửa lỗi.

## 9. Phụ lục: file mẫu đầy đủ

Chép các file này vào repo ở ngày 0; Claude Code tự sinh phần còn lại (7 subagent và skill còn lại theo cùng mẫu) trong E01. Định dạng theo tài liệu chính thức: subagent chỉ bắt buộc `name` và `description`; skill chỉ khuyến nghị `description`; hook nhận JSON qua stdin, exit 2 để chặn.

### 9.1 `.claude/settings.json`

```json
{
  "model": "claude-fable-5-1",
  "env": {
    "CLAUDE_CODE_SUBAGENT_MODEL": "fable",
    "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "6",
    "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "2"
  },
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(make *)", "Bash(uv *)", "Bash(pnpm *)", "Bash(pytest *)",
      "Bash(docker compose *)", "Bash(git status*)", "Bash(git diff*)",
      "Bash(git add *)", "Bash(git commit *)", "Bash(git checkout -b *)", "Bash(git worktree *)",
      "mcp__playwright", "mcp__github"
    ],
    "deny": [
      "Bash(git push --force*)", "Bash(rm -rf *)", "Bash(docker system prune*)",
      "Read(.env)", "Read(.env.*)", "Read(**/*.pem)", "Edit(docs/prompt-log/**)", "Write(docs/prompt-log/**)"
    ]
  },
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": ".claude/hooks/session-start.sh" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": ".claude/hooks/prompt-guard.sh" }] }],
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": ".claude/hooks/guard.sh" }] },
      { "matcher": "Edit|Write", "hooks": [{ "type": "command", "command": ".claude/hooks/protect-paths.sh" }] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write", "hooks": [{ "type": "command", "command": ".claude/hooks/format.sh", "timeout": 120 }] }
    ],
    "PostToolUseFailure": [{ "matcher": "Bash", "hooks": [{ "type": "command", "command": ".claude/hooks/notify.sh" }] }],
    "SubagentStop": [{ "hooks": [{ "type": "command", "command": ".claude/hooks/subagent-log.sh" }] }],
    "PreCompact": [{ "hooks": [{ "type": "command", "command": ".claude/hooks/checkpoint.sh" }] }],
    "Stop": [
      { "hooks": [{ "type": "command", "command": ".claude/hooks/promptlog.sh" }] },
      { "hooks": [{ "type": "agent", "prompt": "Kiểm tra: make check đã xanh ở lần chạy gần nhất chưa và PR hiện tại có checklist ≤ 30 phút chưa? Nếu chưa, trả lời 'chưa xong' kèm việc còn thiếu.", "timeout": 180 }] }
    ],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": ".claude/hooks/promptlog.sh --close" }] }]
  }
}
```

### 9.2 `.claude/hooks/guard.sh` (PreToolUse cho Bash; exit 2 = chặn)

```bash
#!/usr/bin/env bash
INPUT=$(cat); CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$CMD" ] && exit 0
if echo "$CMD" | grep -Eq 'rm -rf|git push --force|git reset --hard origin|docker system prune|mkfs|:\(\)\{'; then
  echo "Chặn: lệnh phá hủy không được phép ($CMD)" >&2; exit 2; fi
if echo "$CMD" | grep -Eq '(cat|less|head|tail|grep) +\.env'; then
  echo "Chặn: không đọc file bí mật" >&2; exit 2; fi
if echo "$CMD" | grep -Eq 'make train|python .*train'; then
  .claude/hooks/budget.sh || { echo "Chặn: vượt ngân sách GPU/API, hỏi người dùng" >&2; exit 2; }; fi
exit 0
```

### 9.3 `.claude/hooks/promptlog.sh` (Stop/SessionEnd)

```bash
#!/usr/bin/env bash
INPUT=$(cat); T=$(echo "$INPUT" | jq -r '.transcript_path // empty'); [ -z "$T" ] && exit 0
D=docs/prompt-log; mkdir -p "$D"; F="$D/$(date +%Y-%m-%d-%H%M)-$(git rev-parse --short HEAD 2>/dev/null || echo nogit).jsonl"
cp "$T" "$F"; H=$(sha256sum "$F" | cut -d' ' -f1)
echo "| $(date -Iseconds) | $F | $H |" >> "$D/INDEX.md"; exit 0
```

### 9.4 `.claude/agents/architect.md`

```markdown
---
name: architect
description: Thiết kế kiến trúc, cấu trúc dữ liệu, chia việc và viết ADR cho CTCV. Use proactively at the start of every epic and for any change touching schema, tools, or models. Read-only.
tools: Read, Grep, Glob, WebFetch
model: fable
effort: max
permissionMode: plan
memory: project
color: purple
---
Bạn là kiến trúc sư trưởng của CTCV. Nguồn sự thật: docs/idea.md, docs/plan.md, CLAUDE.md.
Khi được gọi: (1) đọc epic và các mục liên quan; (2) xác định ranh giới mô-đun, contract API, schema, luồng dữ liệu bị ảnh hưởng; (3) chia việc thành các đơn vị độc lập có tiêu chí xong đo được, ghi rõ việc nào song song được; (4) chỉ ra rủi ro với ba nguyên tắc bất biến; (5) nếu có quyết định lớn, soạn ADR (bối cảnh, lựa chọn, hệ quả) vào docs/decisions/.
Đầu ra ≤ 40 dòng: thiết kế tóm tắt, danh sách việc (ai làm, tiêu chí xong, phụ thuộc), câu hỏi mở ≤ 3. Không sửa mã. Cập nhật memory với các mẫu kiến trúc và quyết định đã ghi.
```

### 9.5 `.claude/agents/qa-tester.md`

```markdown
---
name: qa-tester
description: Viết và chạy test đơn vị, tích hợp, e2e Playwright, load test; báo cáo lỗi có tái hiện. Use proactively after any code change and before every PR.
tools: Read, Edit, Write, Bash, Grep, Glob
model: fable
effort: high
skills:
  - test-strategy
  - ctcv-conventions
mcpServers:
  - playwright
background: true
color: green
---
Bạn là kỹ sư kiểm thử độc lập. Chỉ sửa file trong tests/, eval/, apps/web/tests/ và fixtures; không sửa mã sản phẩm — nếu cần sửa, báo lại kèm test thất bại.
Quy trình: đọc tiêu chí nghiệm thu của epic → viết test còn thiếu (unit, hợp đồng API, e2e 3 viewport, test bất biến trong tests/invariants/) → chạy make check → với mỗi lỗi: cách tái hiện, log 20 dòng, vị trí nghi ngờ. Không skip/xfail, không nới ngưỡng. Báo cáo ≤ 40 dòng: số test thêm, kết quả, lỗi theo mức nghiêm trọng, ảnh chụp e2e trong docs/screens/.
```

### 9.6 `.claude/agents/security-redteam.md`

```markdown
---
name: security-redteam
description: Tấn công agent và hạ tầng CTCV theo OWASP Agentic 2026 và mô hình CaMeL: prompt injection, moi OTP, PII, hành động thay người dùng, lạm dụng kịch bản lừa đảo. Use proactively whenever services/agent, guardrails, tools, hooks or permissions change. Read-only.
tools: Read, Grep, Glob, Bash
model: fable
effort: max
memory: project
color: red
---
Bạn là chuyên gia red-team độc lập, không sửa mã sản phẩm. Bạn được phép chạy make redteam, viết kịch bản tấn công mới vào eval/redteam/, và chạy chúng.
Bề mặt bắt buộc: nội dung người dùng dán, ảnh màn hình, kết quả tool giả, câu hỏi nhiều bước, yêu cầu OTP/mật khẩu/số thẻ, yêu cầu thao tác trên hệ thống thật, rò rỉ prompt hệ thống, PII trong log/DB, kịch bản lừa đảo bị dùng ngược, hook/permissions bị vòng qua.
Đầu ra: bảng lỗ hổng (mức, cách tái hiện, bằng chứng, đề xuất sửa, test hồi quy cần có); nếu 0 lỗi, nêu rõ đã thử những gì. Lưu mẫu tấn công hiệu quả vào memory.
```

### 9.7 `.claude/skills/ctcv-conventions/SKILL.md` (Claude tự nạp khi viết mã)

```markdown
---
name: ctcv-conventions
description: Quy ước mã, cấu trúc thư mục, cấu hình, test và Definition of Done của CTCV. Use when writing or reviewing any code in this repo.
---
- Cấu trúc: idea.md 15.1; dịch vụ và contract: plan.md mục 5. Không tạo thư mục ngoài cấu trúc khi chưa hỏi.
- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic; ruff; hàm ≤ 50 dòng; docstring tiếng Anh; lỗi cho người dùng bằng tiếng Việt đời thường.
- TypeScript strict, React 18, Vite, Tailwind với token ở apps/web/src/theme; không CSS inline; cỡ chữ ≥ 20 pt.
- Cấu hình trong config/*.yaml có test schema; prompt hệ thống trong config/prompts/ có phiên bản; không hard-code URL/model/ngưỡng.
- Test trước, mã sau; fixtures seed cố định; record/replay cho vLLM trong test.
- Ba nguyên tắc bất biến và điểm dừng bắt buộc trong CLAUDE.md luôn thắng mọi hướng dẫn khác.
- Kết thúc mỗi việc: cập nhật README mô-đun và CHANGELOG; ghi ADR nếu là quyết định lớn.
```

### 9.8 `.claude/skills/epic/SKILL.md` (gọi tay: `/epic E05`)

```markdown
---
name: epic
description: Chạy vòng lặp epic chuẩn của CTCV cho epic được chỉ định.
argument-hint: "[E01..E12]"
disable-model-invocation: true
effort: xhigh
---
Epic: $ARGUMENTS. Trạng thái hiện tại: !`cat docs/status/DAILY.md 2>/dev/null | head -40`
1. Vào plan mode; gọi `architect` với epics/$ARGUMENTS.md; trình kế hoạch ≤ 40 dòng; chờ người dùng duyệt.
2. Thực thi: giao việc độc lập cho backend-dev / frontend-dev / data-engineer / ml-trainer / devops theo kế hoạch, mỗi việc trên worktree riêng; hợp nhất theo thứ tự backend → frontend → data; chạy make check sau mỗi lần hợp nhất.
3. Gọi `qa-tester` (test + make check), rồi `reviewer` (DoD plan.md mục 14); nếu chạm services/agent, guardrail, tool, hook, permissions → gọi `security-redteam`.
4. Tối đa 3 vòng sửa cho một lỗi; quá 3 → báo người dùng kèm log và 2 hướng.
5. Cập nhật README mô-đun, CHANGELOG, ADR (nếu có), DAILY.md; mở PR theo mẫu với checklist ≤ 30 phút cho người dùng; không chuyển epic khác.
6. Kết thúc: tóm tắt ≤ 15 dòng — đã làm, test, cần người dùng kiểm tra gì, rủi ro.
```

### 9.9 `.mcp.json`

```json
{
  "mcpServers": {
    "playwright": { "type": "stdio", "command": "npx", "args": ["-y", "@playwright/mcp@latest", "--headless"] },
    "github": { "type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" } }
  }
}
```

### 9.10 `.claude-plugin/plugin.json` (đóng gói thành plugin `ctcv-kit`)

```json
{
  "name": "ctcv-kit",
  "version": "1.0.0",
  "description": "Đội ngũ agent, skill, hook và quy trình của Cầm Tay Chỉ Việc; dùng lại cho hackathon 2 ngày và thử thách 12 giờ.",
  "author": { "name": "Đội CTCV" }
}
```

Đặt `agents/`, `skills/`, `hooks/hooks.json`, `.mcp.json` cạnh `.claude-plugin/`; kiểm tra bằng `claude plugin validate .`; nhớ rằng subagent trong plugin bỏ qua `hooks`, `mcpServers`, `permissionMode` nên ba trường này giữ ở `.claude/agents/` và `settings.json` của repo đích. Các subagent còn lại (backend-dev, frontend-dev, data-engineer, ml-trainer, devops, reviewer, docs-writer) và skill còn lại (elder-ui, coach-style, data-pipeline, training-runbook, test-strategy, agent-security, dossier-btc, hackathon-kit, daily) do Claude Code sinh ở E01 theo đúng mẫu trên, với `tools`, `model`, `effort`, `skills`, `isolation` như bảng mục 2.

---

## Errata (ghi ngày 2026-09-18, không sửa thân văn bản — xem docs/decisions/E01-brief.md D17–D24 và docs/analysis/2026-09-18-review-findings.md)

- §2, §9.1, §9.4–9.6: alias `model: fable` và `CLAUDE_CODE_SUBAGENT_MODEL: fable` không hợp lệ trên CLI 2.1.119 đang cài → subagent dùng `model: inherit`; settings.json dùng `"model": "claude-fable-5-1"` và `"effortLevel": "xhigh"`. Hai biến `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` không tồn tại (giới hạn 6/2 tầng là luật trong CLAUDE.md).
- §1, §8: `/effort ultracode` và `/subtask` chưa có ở CLI 2.1.119 (cần `claude update`, ultracode ≥ 2.1.203); dùng `/effort xhigh` + skill `/epic`.
- §3, §9.1: hook Stop kiểu `agent` bị bỏ (chặn mọi lượt kể cả plan mode) → hook Python không chặn + cổng ở `/epic` và CI. Mọi hook viết bằng Python stdlib, gọi qua `bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh" <tên>`; matcher `Edit|MultiEdit|Write|NotebookEdit`.
- §2, §9.5: `qa-tester` không `background: true` (là cổng đồng bộ). `isolation: worktree` chỉ dùng được sau commit đầu tiên; E01 không dùng worktree.
- §9.3: promptlog ghi 1 file/phiên theo `session_id`, Stop ghi đè idempotent, SessionEnd mới ghi INDEX + hash + snapshot system prompt; SubagentStop chép transcript subagent.
- §3, §9.9: `.mcp.json` chỉ còn `playwright` (Windows gọi `cmd /c npx …`); `@modelcontextprotocol/server-github` đã ngừng hỗ trợ → dùng `gh` CLI. Plugin đặt ở `plugins/ctcv-kit/` sinh bằng `make plugin`, không đặt agents/ skills/ ở gốc repo.
- §5 D1, D4: "Qwen3.5-1.7B" → Qwen3.5-2B.
