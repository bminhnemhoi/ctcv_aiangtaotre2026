from __future__ import annotations

from pathlib import Path

import evidence


def test_snapshot_creates_folder_with_git_state(tmp_path: Path) -> None:
    (tmp_path / "docs" / "status").mkdir(parents=True)
    (tmp_path / "docs" / "status" / "DAILY.md").write_text("# DAILY\n", encoding="utf-8")
    folder = evidence.snapshot(tmp_path, day="2026-09-18")
    assert folder == tmp_path / "docs" / "screens" / "2026-09-18"
    assert (folder / "DAILY.md").read_text(encoding="utf-8") == "# DAILY\n"
    assert not (folder / "last_check.json").exists()
    state = (folder / "git-state.txt").read_text(encoding="utf-8")
    assert "captured_at:" in state and "## head" in state


def test_main_prints_summary(tmp_path: Path, capsys) -> None:
    assert evidence.main(["--root", str(tmp_path), "--day", "2026-01-01"]) == 0
    out = capsys.readouterr().out
    assert "docs" in out and "git-state.txt" in out
    assert "apps/web" in out
