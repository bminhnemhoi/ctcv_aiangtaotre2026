"""PreToolUse guard for the Bash tool (brief §11, D22) — fails CLOSED.

Exit 2 with a Vietnamese reason blocks the command. Any problem parsing the hook
payload or the ``command`` field also blocks (D22). Rules cover destructive
commands (rm -rf in every spelling, forced pushes, hard resets to a remote,
git clean, hook bypasses, docker prune), secret exposure (reading ``.env``/``*.pem``,
``printenv``, bare ``env``/``set``, ``docker compose config`` without
``--no-interpolate``), pipe-to-shell, writes into the prompt log, and the
training budget trigger delegated to ``budget.py``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import budget
from _common import block, project_dir, read_stdin_json, short, utf8_streams

SEGMENT_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
FLAG_TOKEN_RE = re.compile(r"^-[a-zA-Z]+$")
CMD_PREFIX = (
    r"(?:^|[\s;&|(`])(?:sudo\s+(?:-\S+\s+)*)?(?:command\s+|exec\s+|env\s+|xargs\s+(?:-\S+\s+)*)?"
)
RM_RE = re.compile(CMD_PREFIX + r"(?:\\|(?:/\S*/)?)?rm\s+([^|;&`)\n]*)")
GIT_PUSH_RE = re.compile(r"\bgit\s+push\b([^|;&\n]*)")
GIT_CLEAN_RE = re.compile(r"\bgit\s+clean\b([^|;&\n]*)")
GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b([^|;&\n]*)")
GIT_RESET_RE = re.compile(r"\bgit\s+reset\b([^|;&\n]*)")
COMPOSE_CONFIG_RE = re.compile(r"\bdocker(?:\s+|-)compose\b([^|;&\n]*\bconfig\b[^|;&\n]*)")

DESTRUCTIVE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"--no-verify\b"), "bỏ qua hook pre-commit (--no-verify) không được phép"),
    (re.compile(r"(?i)core\.hookspath"), "đổi core.hooksPath (vô hiệu hook git) không được phép"),
    (
        re.compile(r"(?:^|[\s;&|])SKIP=\S*[^|;&\n]*\bgit\s+commit\b"),
        "SKIP=… git commit bỏ qua pre-commit",
    ),
    (re.compile(r"\bpre-commit\s+uninstall\b"), "gỡ pre-commit không được phép"),
    (re.compile(r"\bdocker\s+(?:system|volume)\s+prune\b"), "docker prune xóa dữ liệu/volume"),
    (re.compile(r"\bmkfs(?:\.\w+)?\b"), "mkfs định dạng đĩa"),
    (re.compile(r"(?i)\bformat\s+[a-z]:"), "format ổ đĩa Windows"),
    (re.compile(r"\bdd\b[^|;&\n]*\bof=/dev/"), "dd ghi thẳng lên thiết bị"),
    (re.compile(r":\(\)\s*\{"), "fork bomb"),
    (
        re.compile(
            r"\b(?:curl|wget|Invoke-WebRequest|iwr)\b[^|\n]*\|\s*(?:sudo\s+)?"
            r"(?:bash|sh|zsh|dash|ksh|pwsh|powershell|python3?|iex|Invoke-Expression)\b"
        ),
        "tải về rồi thực thi qua pipe (curl|sh)",
    ),
    (
        re.compile(r"(?i)\bRemove-Item\b(?=[^|;&\n]*-Rec\w*)(?=[^|;&\n]*-Fo\w*)"),
        "Remove-Item -Recurse -Force (rm -rf kiểu PowerShell)",
    ),
    (re.compile(r"(?i)\b(?:rd|rmdir)\s+(?:/\w\s+)*/s\b"), "rd /s xóa đệ quy"),
    (re.compile(r"(?i)\bdel\s+(?:/\w\s+)*/[sq]\b"), "del /s|/q xóa hàng loạt"),
)

SECRET_EXPOSURE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bprintenv\b"), "printenv in toàn bộ biến môi trường (có secret)"),
    (
        re.compile(r"(?i)(?:\$\(|`)\s*(?:env|set|printenv)\s*(?:\)|`)"),
        "$(env)/$(set) rò rỉ biến môi trường",
    ),
    (
        re.compile(
            r"(?i)\b(?:echo|printf|write-host|write-output)\b[^|;&\n]*"
            r"\$(?:env:|\{)?\w*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|ACCESS_KEY|PRIVATE_KEY)\w*"
        ),
        "in biến chứa secret ra màn hình",
    ),
    (
        re.compile(r"(?:dict\(os\.environ\)|os\.environ\.items\(\)|print\(os\.environ\))"),
        "in os.environ (có secret)",
    ),
    (
        re.compile(r"(?i)(?:^|[\s;&|(])(?:Get-ChildItem|gci|ls|dir)\s+env:"),
        "liệt kê biến môi trường PowerShell",
    ),
)

BARE_ENV_RE = re.compile(r"(?i)^\s*(?:env|set|export|declare\s+-x)\s*$")
ENV_TOKEN_RE = re.compile(r"(?:^|[\s/\"'=])\.env(?:\.[\w-]+)?\b")
HIDDEN_GLOB_RE = re.compile(r"(?:^|[\s/\"'=])\.[eE]?[nN]?[*?]")
KEY_TOKEN_RE = re.compile(r"\S+\.pem\b|\bid_rsa\b|\bid_ed25519\b")
QUOTED_RE = re.compile(r"\"[^\"]*\"|'[^']*'")
READER_RE = re.compile(
    r"(?i)(?:^|[\s;&|(`])(?:sudo\s+)?(?:cat|bat|less|more|head|tail|grep|egrep|fgrep|rg|ag|awk|gawk"
    r"|sed|cut|sort|uniq|nl|od|xxd|hexdump|strings|tac|wc|tee|source|type|Get-Content|gc"
    r"|Select-String|sls|python3?(?:\.exe)?\s+-c|node\s+-e|perl\s+-e|ruby\s+-e)\b|(?:^|\s)\.\s"
)
STDIN_REDIRECT_RE = re.compile(r"<\s*[\"']?\S*\.env\b")
PROTECTED_WRITE_TARGETS = re.compile(r"docs/prompt-log|data/registry/\S*\.lock")
WRITE_VERB_RE = re.compile(
    r"(?:^|[\s;&|])(?:rm|mv|cp|tee|touch|truncate|dd|sed\s+-i\S*|python3?\s+-c|"
    r"git\s+(?:rm|checkout|restore|clean))\b"
)
REDIRECT_RE = re.compile(r">{1,2}\s*[\"']?\S*(?:docs/prompt-log|data/registry/\S*\.lock)")
BUDGET_TRIGGER_RE = re.compile(
    r"^(?:make\s+(?:train|data|finetune)\b|uv\s+run\s+(?:python\s+)?-m\s+ctcv_training\b"
    r"|uv\s+run\s+python\s+training/)"
)


def _rm_flags(args: str) -> tuple[bool, bool]:
    """Return ``(recursive, force)`` for the argument string of an ``rm`` call."""
    recursive = force = False
    for token in args.split():
        if token == "--":
            break
        if token in ("--recursive",):
            recursive = True
        elif token in ("--force",):
            force = True
        elif FLAG_TOKEN_RE.match(token):
            letters = token[1:]
            recursive |= "r" in letters or "R" in letters
            force |= "f" in letters
    return recursive, force


def check_rm(command: str) -> str | None:
    """Block ``rm`` with recursive + force in any order or spelling."""
    for match in RM_RE.finditer(command):
        recursive, force = _rm_flags(match.group(1))
        if recursive and force:
            return "rm đệ quy + ép buộc (rm -rf và mọi biến thể) không được phép"
    return None


def check_git(command: str) -> str | None:
    """Block forced pushes, hard resets to a remote, git clean -f and commit -n."""
    for match in GIT_PUSH_RE.finditer(command):
        args = match.group(1)
        if re.search(r"\s--force(?:-with-lease|-if-includes)?(?:=\S*)?\b", args):
            return "git push --force / --force-with-lease không được phép"
        if re.search(r"\s-[a-zA-Z]*f[a-zA-Z]*(?=\s|$)", args) or re.search(r"\s\+\S", args):
            return "git push -f (hoặc refspec +ref) không được phép"
    for match in GIT_RESET_RE.finditer(command):
        args = match.group(1)
        if "--hard" in args and re.search(r"\b(?:origin|upstream)\b|@\{u(?:pstream)?\}", args):
            return "git reset --hard về remote xóa mọi thay đổi cục bộ"
    for match in GIT_CLEAN_RE.finditer(command):
        args = match.group(1)
        if re.search(r"\s-[a-zA-Z]*f[a-zA-Z]*(?=\s|$)|\s--force\b", args) and not re.search(
            r"\s-[a-zA-Z]*n[a-zA-Z]*(?=\s|$)|--dry-run", args
        ):
            return "git clean -f xóa file chưa theo dõi"
    for match in GIT_COMMIT_RE.finditer(command):
        for token in QUOTED_RE.sub(" ", match.group(1)).split():
            if FLAG_TOKEN_RE.match(token) and "n" in token[1:]:
                return "git commit -n (= --no-verify) bỏ qua pre-commit"
    return None


def check_patterns(command: str, rules: tuple[tuple[re.Pattern[str], str], ...]) -> str | None:
    """Return the reason of the first matching rule."""
    for pattern, reason in rules:
        if pattern.search(command):
            return reason
    return None


def check_segments(command: str) -> str | None:
    """Per-segment rules: bare env/set, docker compose config, .env reads."""
    for segment in SEGMENT_SPLIT_RE.split(command):
        if not segment.strip():
            continue
        if BARE_ENV_RE.match(segment):
            return "lệnh env/set/export đứng một mình in toàn bộ biến môi trường"
        if READER_RE.search(segment):
            if ENV_TOKEN_RE.search(segment) or HIDDEN_GLOB_RE.search(segment):
                return "không đọc file .env / file ẩn bằng cat/grep/head/… (secret)"
            if KEY_TOKEN_RE.search(segment):
                return "không đọc khóa riêng (*.pem, *.key, id_rsa)"
        if (WRITE_VERB_RE.search(segment) and PROTECTED_WRITE_TARGETS.search(segment)) or (
            REDIRECT_RE.search(segment)
        ):
            return "docs/prompt-log/** và data/registry/*.lock chỉ do hook/pipeline ghi"
    for match in COMPOSE_CONFIG_RE.finditer(command):
        if "--no-interpolate" not in match.group(1):
            return "docker compose config in secret đã nội suy — thêm --no-interpolate"
    if STDIN_REDIRECT_RE.search(command):
        return "không đọc .env qua chuyển hướng stdin"
    return None


def check_budget(command: str, root: Path) -> str | None:
    """Run the training budget gate when a segment matches the trigger (D22)."""
    for segment in SEGMENT_SPLIT_RE.split(command):
        if BUDGET_TRIGGER_RE.match(segment.strip()):
            problems = budget.check(root)
            if problems:
                return "vượt ngân sách huấn luyện — hỏi người dùng trước: " + "; ".join(problems)
            return None
    return None


def inspect(command: str, root: Path) -> str | None:
    """Return a block reason for ``command`` or ``None`` when it is allowed."""
    checks = (
        check_rm(command),
        check_git(command),
        check_patterns(command, DESTRUCTIVE),
        check_patterns(command, SECRET_EXPOSURE),
        check_segments(command),
        check_budget(command, root),
    )
    return next((reason for reason in checks if reason), None)


def main() -> int:
    """Hook entry point: read payload, fail closed on parse errors, exit 2 to block."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        block(f"guard không đọc được dữ liệu hook ({error}) — chặn để an toàn (fail-closed)")
    if data.get("tool_name", "Bash") != "Bash":
        return 0
    tool_input = data.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if command is None or not isinstance(command, str):
        block("guard không đọc được trường command — chặn để an toàn (fail-closed)")
    if not command.strip():
        return 0
    reason = inspect(command, project_dir(data))
    if reason:
        block(f"{reason}. Lệnh: {short(command, 160)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
