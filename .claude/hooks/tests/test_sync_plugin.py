"""Tests for ``scripts/sync_plugin.py`` (plugin ctcv-kit generated from ``.claude/``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_plugin  # noqa: E402

AGENT = """---
name: demo
description: Demo agent.
tools: Read, Grep
model: inherit
permissionMode: plan
mcpServers:
  - playwright
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: echo hi
memory: project
skills:
  - demo-skill
color: blue
---
Thân agent.
"""
SETTINGS = {
    "model": "claude-fable-5-1",
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh" guard',
                        "timeout": 30,
                    }
                ],
            }
        ],
        "SessionEnd": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh" promptlog --close'
                        ),
                    }
                ]
            }
        ],
    },
}


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "agents" / "demo.md").write_text(AGENT, encoding="utf-8")
    skill = claude / "skills" / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: x\n---\nnội dung\n", "utf-8"
    )
    (skill / "ref.md").write_text("tham chiếu\n", encoding="utf-8")
    hooks = claude / "hooks"
    (hooks / "tests").mkdir(parents=True)
    (hooks / "run.sh").write_text("#!/usr/bin/env bash\nexec python x\n", encoding="utf-8")
    (hooks / "guard.py").write_text("print('guard')\n", encoding="utf-8")
    (hooks / "tests" / "test_x.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (claude / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
    (tmp_path / ".mcp.json").write_text('{"mcpServers": {"playwright": {}}}\n', "utf-8")
    return tmp_path


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_strip_frontmatter_keys_removes_blocks_and_keeps_rest() -> None:
    data = yaml.safe_load(sync_plugin.convert_agent(AGENT).split("---\n", 2)[1])
    assert set(data) == {"name", "description", "tools", "model", "memory", "skills", "color"}
    assert data["skills"] == ["demo-skill"] and data["tools"] == "Read, Grep"


def test_build_generates_complete_plugin(mini_repo: Path) -> None:
    out = mini_repo / "plugins" / "ctcv-kit"
    summary = sync_plugin.build(mini_repo, out)
    assert summary == {"agents": ["demo"], "skills": ["demo-skill"], "hook_events": 2, "mcp": True}
    manifest = json.loads((out / ".claude-plugin" / "plugin.json").read_text("utf-8"))
    assert manifest["name"] == "ctcv-kit" and manifest["version"] and manifest["author"]["name"]
    agent = _frontmatter(out / "agents" / "demo.md")
    for key in sync_plugin.STRIPPED_AGENT_KEYS:
        assert key not in agent
    assert (out / "agents" / "demo.md").read_text("utf-8").endswith("---\nThân agent.\n")
    assert (out / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert (out / "skills" / "demo-skill" / "ref.md").is_file()
    hooks = json.loads((out / "hooks" / "hooks.json").read_text("utf-8"))["hooks"]
    commands = [h["command"] for entries in hooks.values() for e in entries for h in e["hooks"]]
    assert commands == [
        'bash "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" guard',
        'bash "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" promptlog --close',
    ]
    assert hooks["PreToolUse"][0]["matcher"] == "Bash"
    assert hooks["PreToolUse"][0]["hooks"][0]["timeout"] == 30
    assert (out / "hooks" / "run.sh").is_file() and (out / "hooks" / "guard.py").is_file()
    assert not (out / "hooks" / "tests").exists()
    assert json.loads((out / ".mcp.json").read_text("utf-8"))["mcpServers"] == {"playwright": {}}
    assert "ctcv-kit" in (out / "README.md").read_text("utf-8")


def test_check_mode_detects_drift(mini_repo: Path) -> None:
    out = mini_repo / "plugins" / "ctcv-kit"
    assert sync_plugin.main(["--root", str(mini_repo), "--check"]) == 1
    assert sync_plugin.main(["--root", str(mini_repo)]) == 0
    assert sync_plugin.main(["--root", str(mini_repo), "--check"]) == 0
    (out / "agents" / "demo.md").write_text("---\nname: demo\n---\nkhác\n", encoding="utf-8")
    assert sync_plugin.check(mini_repo, out) == ["agents/demo.md"]
    (mini_repo / ".claude" / "agents" / "new.md").write_text(AGENT.replace("demo", "new"), "utf-8")
    assert "agents/new.md" in sync_plugin.check(mini_repo, out)


def test_committed_plugin_matches_dot_claude() -> None:
    diffs = sync_plugin.check(REPO_ROOT, REPO_ROOT / "plugins" / "ctcv-kit")
    assert diffs == [], f"plugins/ctcv-kit lệch .claude/ — chạy `make plugin`: {diffs}"


def test_committed_plugin_agents_have_no_ignored_keys() -> None:
    plugin_agents = REPO_ROOT / "plugins" / "ctcv-kit" / "agents"
    files = list(plugin_agents.glob("*.md"))
    assert len(files) >= 10
    for path in files:
        data = _frontmatter(path)
        assert data["model"] == "inherit"
        for key in sync_plugin.STRIPPED_AGENT_KEYS:
            assert key not in data, f"{path.name}: {key}"
