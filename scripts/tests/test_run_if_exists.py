from __future__ import annotations

from pathlib import Path

import pytest
import run_if_exists


def test_missing_module_exits_zero_with_notice(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The harness exists since E01; simulate "not implemented yet" instead of relying on repo state.
    monkeypatch.setattr(run_if_exists, "is_runnable", lambda name: False)
    assert run_if_exists.main(["ctcv_eval.harness", "--quick"]) == 0
    out = capsys.readouterr().out
    assert "CHƯA HIỆN THỰC" in out
    assert "ctcv_eval.harness" in out
    assert "epics/E05.md" in out


def test_unknown_module_uses_default_epic(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_if_exists.main(["no_such_pkg.mod"]) == 0
    assert "epics/E01.md" in capsys.readouterr().out


def test_no_args_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_if_exists.main([]) == 2
    assert "Cách dùng" in capsys.readouterr().err


def test_is_runnable_handles_bad_names() -> None:
    assert run_if_exists.is_runnable("json.tool")  # plain module
    assert run_if_exists.is_runnable("venv")  # package with __main__.py
    assert not run_if_exists.is_runnable("json")  # package without __main__.py
    assert not run_if_exists.is_runnable("json.nope")
    assert not run_if_exists.is_runnable("")


def test_package_without_main_is_not_runnable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    (tmp_path / "fake_pkg").mkdir()
    (tmp_path / "fake_pkg" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert not run_if_exists.is_runnable("fake_pkg")
    assert run_if_exists.main(["fake_pkg"]) == 0
    assert "CHƯA HIỆN THỰC" in capsys.readouterr().out
    (tmp_path / "fake_pkg" / "__main__.py").write_text("print('RAN')", encoding="utf-8")
    assert run_if_exists.is_runnable("fake_pkg")


def test_runs_module_and_propagates_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    (tmp_path / "fake_harness.py").write_text(
        "import sys\nprint('ARGS', sys.argv[1:])\nsys.exit(3 if '--quick' in sys.argv else 0)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    assert run_if_exists.main(["fake_harness", "--quick"]) == 3
    assert "ARGS ['--quick']" in capsys.readouterr().out
    assert run_if_exists.main(["fake_harness"]) == 0


def test_non_int_exit_code_becomes_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "fake_bad_exit.py").write_text("import sys\nsys.exit('lỗi')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert run_if_exists.main(["fake_bad_exit"]) == 1
