from __future__ import annotations

import json
from pathlib import Path

import pytest
import write_last_check


def test_writes_payload_outside_git(tmp_path: Path) -> None:
    path = write_last_check.write_last_check(tmp_path, ok=True, quick=True)
    assert path == tmp_path / "docs" / "status" / "last_check.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"ts", "git_head", "ok", "quick"}
    assert data["ok"] is True
    assert data["quick"] is True
    assert data["git_head"] == "nogit"
    assert data["ts"].endswith("+00:00")


def test_git_head_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        write_last_check.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("x"))
    )
    assert write_last_check.git_head(tmp_path) == "nogit"


def test_main_flags_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("QUICK", "1")
    assert write_last_check.main(["--root", str(tmp_path), "--fail"]) == 0
    data = json.loads(
        (tmp_path / "docs" / "status" / "last_check.json").read_text(encoding="utf-8")
    )
    assert data["ok"] is False
    assert data["quick"] is True
    assert "đỏ" in capsys.readouterr().out


def test_real_repo_head_is_hash_or_nogit() -> None:
    head = write_last_check.git_head(write_last_check.REPO_ROOT)
    assert head == "nogit" or len(head) == 40
