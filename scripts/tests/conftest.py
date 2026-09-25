"""Make the standalone scripts importable as modules for their tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def docs_root(tmp_path: Path) -> Path:
    """A minimal repo layout that passes check_docs and doctor's file checks."""
    (tmp_path / "README.md").write_text(
        "# X\n\n## Chạy nhanh\n\n## Yêu cầu máy\n\n## Cấu trúc kho mã\n\n"
        "## Lệnh chuẩn\n\n## Tài liệu\n\n## Giấy phép\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- E01 khung repo\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "prompt-log").mkdir(parents=True)
    (tmp_path / "docs" / "prompt-log" / "INDEX.md").write_text(
        "| ts | file | sha256 | git_head |\n| --- | --- | --- | --- |\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "template").mkdir()
    for name in ("idea.md", "plan.md", "prompt.md"):
        (tmp_path / "docs" / name).write_text("# doc\n", encoding="utf-8")
    (tmp_path / "docs" / "template" / "AI2026_Mau_ho_so.docx").write_bytes(b"PK")
    (tmp_path / ".env.example").write_text(
        "A=1\nB=CHANGE_ME\n# c\nHF_TOKEN=CHANGE_ME\n", encoding="utf-8"
    )
    return tmp_path
