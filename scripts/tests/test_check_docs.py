from __future__ import annotations

from pathlib import Path

import check_docs
import pytest


def test_good_layout_has_no_problems(docs_root: Path) -> None:
    assert check_docs.run_checks(docs_root) == []
    assert check_docs.main(["--root", str(docs_root)]) == 0


def test_missing_readme_section(docs_root: Path) -> None:
    readme = docs_root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("## Giấy phép\n", ""), encoding="utf-8"
    )
    problems = check_docs.check_readme(docs_root)
    assert len(problems) == 1
    assert "Giấy phép" in problems[0]


def test_missing_readme_file(tmp_path: Path) -> None:
    assert check_docs.check_readme(tmp_path) == ["Thiếu README.md ở gốc kho mã."]


def test_changelog_without_unreleased(docs_root: Path) -> None:
    (docs_root / "CHANGELOG.md").write_text("# Changelog\n\n## [0.1.0]\n\n- x\n", encoding="utf-8")
    assert check_docs.check_changelog(docs_root) == ["CHANGELOG.md không có mục '## [Unreleased]'."]


def test_changelog_unreleased_without_entries(docs_root: Path) -> None:
    (docs_root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [0.1.0]\n\n- old\n", encoding="utf-8"
    )
    problems = check_docs.check_changelog(docs_root)
    assert len(problems) == 1
    assert "[Unreleased]" in problems[0]


def test_changelog_missing(tmp_path: Path) -> None:
    assert check_docs.check_changelog(tmp_path) == ["Thiếu CHANGELOG.md ở gốc kho mã."]


def test_prompt_log_index_missing_or_empty(docs_root: Path) -> None:
    index = docs_root / "docs" / "prompt-log" / "INDEX.md"
    index.write_text("  \n", encoding="utf-8")
    assert "rỗng" in check_docs.check_prompt_log_index(docs_root)[0]
    index.unlink()
    assert "Thiếu docs/prompt-log/INDEX.md" in check_docs.check_prompt_log_index(docs_root)[0]


def test_main_reports_all_problems(docs_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (docs_root / "README.md").unlink()
    (docs_root / "docs" / "prompt-log" / "INDEX.md").unlink()
    assert check_docs.main(["--root", str(docs_root)]) == 1
    out = capsys.readouterr().out
    assert out.count("LỖI:") == 2
    assert "2 vấn đề" in out


def test_real_repo_passes() -> None:
    assert check_docs.run_checks(check_docs.REPO_ROOT) == []
