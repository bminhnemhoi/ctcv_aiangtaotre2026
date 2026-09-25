"""Generate ``plugins/ctcv-kit/`` from ``.claude/`` (brief §11, prompt.md §9.10).

The plugin packages the CTCV agents, skills, hooks and MCP config so the team can
reuse them in the hackathon repo (``claude --plugin-dir plugins/ctcv-kit``).

Output (all files regenerated, never edited by hand — ``make plugin``):

* ``.claude-plugin/plugin.json`` — manifest (name, version, description, author).
* ``agents/*.md`` — copies with the frontmatter keys ``hooks``, ``mcpServers`` and
  ``permissionMode`` removed (plugins ignore them; keep them in ``.claude/agents``).
* ``skills/<name>/**`` — verbatim copies.
* ``hooks/hooks.json`` — the ``hooks`` block of ``settings.json`` with every command
  rewritten to ``bash "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" <name>``.
* ``hooks/run.sh``, ``hooks/*.py`` — the hook implementations (tests excluded).
* ``.mcp.json`` — copy of the repo file.
* ``README.md`` — generated usage notes.

Standard library only. ``--check`` regenerates into a temporary directory and
exits 1 when the committed plugin differs (for CI).
"""

from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

PLUGIN_NAME = "ctcv-kit"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = (
    "Đội ngũ agent, skill, hook và quy trình của Cầm Tay Chỉ Việc; "
    "dùng lại cho hackathon 2 ngày và thử thách 12 giờ."
)
PLUGIN_AUTHOR = {"name": "Đội CTCV"}
STRIPPED_AGENT_KEYS = ("hooks", "mcpServers", "permissionMode")
PROJECT_HOOK_PREFIX = 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh"'
PLUGIN_HOOK_PREFIX = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh"'
HOOK_IGNORE = shutil.ignore_patterns("tests", "__pycache__", "*.pyc", "README.md")
SKILL_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z][\w-]*):")
ENCODING = "utf-8"


def repo_root() -> Path:
    """Repository root = parent of ``scripts/``."""
    return Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------------- agents
def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Return ``(frontmatter, body)`` for a ``---``-delimited file, else ``None``."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    return text[4:end], text[end + len("\n---\n") :]


def strip_frontmatter_keys(frontmatter: str, keys: tuple[str, ...]) -> str:
    """Drop top-level ``keys`` (with their indented/list continuation lines)."""
    kept: list[str] = []
    skipping = False
    for line in frontmatter.splitlines():
        match = FRONTMATTER_KEY_RE.match(line)
        if match:
            skipping = match.group(1) in keys
        elif not (line.startswith((" ", "\t", "- ")) or not line.strip()):
            skipping = False
        if not skipping:
            kept.append(line)
    return "\n".join(kept).strip("\n") + "\n"


def convert_agent(text: str) -> str:
    """Agent file content for the plugin (frontmatter stripped of plugin-ignored keys)."""
    parts = split_frontmatter(text)
    if parts is None:
        return text
    frontmatter, body = parts
    return f"---\n{strip_frontmatter_keys(frontmatter, STRIPPED_AGENT_KEYS)}---\n{body}"


def write_agents(claude_dir: Path, out: Path) -> list[str]:
    """Copy ``.claude/agents/*.md`` into ``out/agents`` converted; return names."""
    names: list[str] = []
    target = out / "agents"
    target.mkdir(parents=True, exist_ok=True)
    for src in sorted((claude_dir / "agents").glob("*.md")):
        (target / src.name).write_text(convert_agent(src.read_text(ENCODING)), ENCODING)
        names.append(src.stem)
    return names


# ----------------------------------------------------------------------------- skills / hooks / mcp
def write_skills(claude_dir: Path, out: Path) -> list[str]:
    """Copy every ``.claude/skills/<name>/`` directory verbatim; return names."""
    names: list[str] = []
    src_root = claude_dir / "skills"
    target = out / "skills"
    target.mkdir(parents=True, exist_ok=True)
    if not src_root.is_dir():
        return names
    for src in sorted(p for p in src_root.iterdir() if (p / "SKILL.md").is_file()):
        shutil.copytree(src, target / src.name, ignore=SKILL_IGNORE, dirs_exist_ok=True)
        names.append(src.name)
    return names


def rewrite_command(command: str) -> str:
    """Point a settings.json hook command at the plugin's ``hooks/run.sh``."""
    if command.startswith(PROJECT_HOOK_PREFIX):
        return PLUGIN_HOOK_PREFIX + command[len(PROJECT_HOOK_PREFIX) :]
    return command.replace("$CLAUDE_PROJECT_DIR/.claude/hooks", "${CLAUDE_PLUGIN_ROOT}/hooks")


def convert_hooks(settings: dict) -> dict:
    """Build the ``hooks.json`` document from the ``hooks`` block of settings.json."""
    hooks = json.loads(json.dumps(settings.get("hooks", {})))
    for entries in hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command" and isinstance(hook.get("command"), str):
                    hook["command"] = rewrite_command(hook["command"])
    return {
        "description": (
            "Hook CTCV (Python stdlib, chạy qua hooks/run.sh) — sinh từ .claude/settings.json"
        ),
        "hooks": hooks,
    }


def write_hooks(claude_dir: Path, out: Path) -> int:
    """Copy hook scripts and write ``hooks/hooks.json``; return number of events."""
    target = out / "hooks"
    if (claude_dir / "hooks").is_dir():
        shutil.copytree(claude_dir / "hooks", target, ignore=HOOK_IGNORE, dirs_exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    settings = json.loads((claude_dir / "settings.json").read_text(ENCODING))
    document = convert_hooks(settings)
    (target / "hooks.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", ENCODING
    )
    return len(document["hooks"])


def write_mcp(root: Path, out: Path) -> bool:
    """Copy the repo ``.mcp.json`` when present."""
    src = root / ".mcp.json"
    if not src.is_file():
        return False
    (out / ".mcp.json").write_text(src.read_text(ENCODING), ENCODING)
    return True


def write_manifest(out: Path) -> None:
    """Write ``.claude-plugin/plugin.json`` (prompt.md §9.10)."""
    manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "license": "Apache-2.0",
        "keywords": ["ctcv", "agents", "skills", "hooks", "hackathon"],
    }
    (out / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (out / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", ENCODING
    )


def render_readme(agents: list[str], skills: list[str], events: int, has_mcp: bool) -> str:
    """README content for the generated plugin (Vietnamese, regenerated every run)."""
    mcp_line = (
        "- `.mcp.json`: chỉ `playwright` (Windows: `cmd /c npx …`; Linux thêm ở user scope: "
        "`claude mcp add playwright -- npx -y @playwright/mcp@latest --headless`)."
        if has_mcp
        else "- Không có `.mcp.json`."
    )
    return (
        f"# {PLUGIN_NAME} — plugin Claude Code của Cầm Tay Chỉ Việc\n\n"
        "**File sinh tự động** bởi `scripts/sync_plugin.py` (`make plugin`) từ `.claude/` — "
        "không sửa tay; sửa ở `.claude/` rồi chạy lại. "
        "Kiểm: `claude plugin validate plugins/ctcv-kit`.\n\n"
        "## Cài vào repo mới (hackathon 2 ngày, thử thách 12 giờ)\n"
        "```\n"
        "claude --plugin-dir /đường/dẫn/ctcv/plugins/ctcv-kit\n"
        "```\n"
        "hoặc thêm thư mục này vào một marketplace nội bộ rồi "
        "`claude plugin install ctcv-kit@<marketplace>`.\n\n"
        "## Nội dung\n"
        f"- `agents/` ({len(agents)}): {', '.join(agents)}. "
        "Frontmatter đã bỏ `hooks`, `mcpServers`, `permissionMode` (plugin không nhận ba "
        "trường này) — repo đích cần đặt lại trong `.claude/agents/` hoặc `settings.json` "
        "của nó nếu muốn `architect` ở plan mode và `frontend-dev`/`qa-tester` dùng MCP "
        "playwright.\n"
        f"- `skills/` ({len(skills)}): {', '.join(skills)}.\n"
        f"- `hooks/hooks.json` ({events} sự kiện) + `hooks/run.sh` + `hooks/*.py`: lệnh dùng "
        "`${CLAUDE_PLUGIN_ROOT}/hooks/run.sh`; hook ghi vào `docs/status/`, "
        "`docs/prompt-log/` của repo đích (tạo hai thư mục này; `protect-paths` cần marker "
        "`.claude/BOOTSTRAP` khi bootstrap).\n"
        f"{mcp_line}\n\n"
        "## Repo đích cần có\n"
        "`CLAUDE.md` (ba nguyên tắc bất biến, điểm dừng, Delegation), `.claude/settings.json` "
        "với `permissions` allow/deny của CTCV, `Makefile` có `check`/`redteam`/`daily`, "
        "`config/allowed-deps.yaml`, `training/budget.json` (hook budget tự tạo mặc định). "
        "Python ≥ 3.10 trên PATH cho hook.\n"
    )


def build(root: Path, out: Path) -> dict[str, object]:
    """Regenerate the plugin at ``out`` from ``root/.claude``; return a summary."""
    claude_dir = root / ".claude"
    if not (claude_dir / "settings.json").is_file():
        raise FileNotFoundError(f"không thấy {claude_dir / 'settings.json'}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    write_manifest(out)
    agents = write_agents(claude_dir, out)
    skills = write_skills(claude_dir, out)
    events = write_hooks(claude_dir, out)
    has_mcp = write_mcp(root, out)
    (out / "README.md").write_text(render_readme(agents, skills, events, has_mcp), ENCODING)
    return {"agents": agents, "skills": skills, "hook_events": events, "mcp": has_mcp}


def _tree_differs(left: Path, right: Path) -> list[str]:
    """Relative paths that differ between two directory trees (recursive)."""
    diffs: list[str] = []

    def walk(cmp: filecmp.dircmp, prefix: str) -> None:
        for name in cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files:
            diffs.append(prefix + name)
        for name, sub in cmp.subdirs.items():
            walk(sub, f"{prefix}{name}/")

    walk(filecmp.dircmp(left, right, ignore=["__pycache__"]), "")
    return sorted(diffs)


def check(root: Path, out: Path) -> list[str]:
    """Return the paths where the committed plugin differs from a fresh build."""
    if not out.is_dir():
        return ["<thiếu thư mục plugin>"]
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / PLUGIN_NAME
        build(root, fresh)
        return _tree_differs(fresh, out)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Sinh plugins/ctcv-kit từ .claude/")
    parser.add_argument("--root", type=Path, default=repo_root(), help="gốc repo")
    parser.add_argument("--out", type=Path, default=None, help="thư mục plugin đầu ra")
    parser.add_argument(
        "--check", action="store_true", help="chỉ kiểm, không ghi (exit 1 nếu lệch)"
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    out = (args.out or root / "plugins" / PLUGIN_NAME).resolve()
    if args.check:
        diffs = check(root, out)
        if diffs:
            print("plugin ctcv-kit LỆCH so với .claude/ — chạy `make plugin`: " + ", ".join(diffs))
            return 1
        print("plugin ctcv-kit: đồng bộ với .claude/")
        return 0
    summary = build(root, out)
    print(
        f"plugin ctcv-kit: {len(summary['agents'])} agent, {len(summary['skills'])} skill, "
        f"{summary['hook_events']} sự kiện hook, mcp={'có' if summary['mcp'] else 'không'} → "
        f"{out.relative_to(root).as_posix() if out.is_relative_to(root) else out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
