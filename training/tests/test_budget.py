"""Budget gate: per-job and cumulative limits, spent accumulation, fail-closed, CLI exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctcv_training import budget
from ctcv_training.budget import Decision, check, evaluate, record_spend


def test_module_is_stdlib_only() -> None:
    """The Claude Code hook imports this outside the venv: no workspace or third-party imports."""
    source = Path(budget.__file__).read_text(encoding="utf-8")
    for forbidden in ("ctcv_core", "yaml", "pydantic", "jsonschema"):
        assert f"import {forbidden}" not in source and f"from {forbidden}" not in source


def test_real_budget_file_matches_plan(repo_root: Path) -> None:
    data = json.loads((repo_root / "training" / "budget.json").read_text(encoding="utf-8"))
    assert data["gpu_hours_total_limit"] == 300
    assert data["gpu_hours_per_job_limit"] == 20
    assert data["api_budget_vnd"] == 2_000_000
    assert data["api_total_limit_vnd"] == data["api_budget_vnd"]  # alias read by the hook
    assert data["api_per_task_limit_vnd"] == 500_000
    assert data["spent"] == {"gpu_hours": 0, "api_vnd": 0}
    assert data["updated_at"]
    decision = check(3, path=repo_root / "training" / "budget.json")
    assert decision.allowed and decision.gpu_hours_remaining == 297


@pytest.mark.parametrize(
    ("hours", "api", "allowed", "fragment"),
    [
        (3, 0, True, ""),
        (20, 500_000, True, ""),  # exactly at the per-job limits
        (20.5, 0, False, "giờ/job"),
        (0, 500_001, False, "đ/tác vụ"),
        (25, 900_000, False, "giờ/job"),
    ],
)
def test_per_job_limits(
    budget_file, hours: float, api: float, allowed: bool, fragment: str
) -> None:
    decision = check(hours, api, path=budget_file())
    assert decision.allowed is allowed
    assert isinstance(decision, Decision)
    if fragment:
        assert any(fragment in r for r in decision.reasons)
        assert "VƯỢT NGÂN SÁCH" in decision.message()
    else:
        assert decision.reasons == [] and "Trong hạn mức" in decision.message()


def test_cumulative_limits_use_spent(budget_file) -> None:
    path = budget_file(gpu_spent=290, api_spent=1_800_000)
    ok = check(10, 200_000, path=path)
    assert ok.allowed and ok.gpu_hours_remaining == 0 and ok.api_vnd_remaining == 0
    over = check(11, 0, path=path)
    assert not over.allowed and any("tổng GPU" in r for r in over.reasons)
    over_api = check(1, 200_001, path=path)
    assert not over_api.allowed and any("tổng API" in r for r in over_api.reasons)


def test_record_spend_accumulates_and_stamps(budget_file) -> None:
    path = budget_file(gpu_spent=290)
    record_spend(2.5, 100_000, path=path, job_name="planner-sft")
    data = record_spend(1.5, 50_000, path=path)
    assert data["spent"] == {"gpu_hours": 294.0, "api_vnd": 150_000}
    assert data["updated_at"] != "2026-09-18T00:00:00+00:00"
    assert data["last_job"]["name"] == "planner-sft"
    assert check(6, path=path).allowed and not check(6.5, path=path).allowed


@pytest.mark.parametrize("bad", ["{bad", "[]", '{"spent": 1}', '{"spent": {"gpu_hours": -1}}'])
def test_malformed_file_fails_closed(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "budget.json"
    path.write_text(bad, encoding="utf-8")
    decision = check(1, path=path)
    assert not decision.allowed and "budget.json lỗi" in decision.reasons[0]


def test_missing_file_fails_closed(tmp_path: Path) -> None:
    decision = check(1, path=tmp_path / "none.json")
    assert not decision.allowed and "thiếu file" in decision.reasons[0]


def test_alias_mismatch_is_rejected(budget_file) -> None:
    path = budget_file(api_budget_vnd=2_000_000, api_total_limit_vnd=1_000_000)
    decision = check(1, path=path)
    assert not decision.allowed and "api_total_limit_vnd" in decision.reasons[0]


def test_negative_estimates_are_rejected() -> None:
    with pytest.raises(ValueError, match="không được âm"):
        evaluate({"spent": {}}, -1)


def test_defaults_when_keys_absent() -> None:
    decision = evaluate({}, 20, 500_000)
    assert decision.allowed and decision.gpu_hours_remaining == 280
    assert not evaluate({}, 21).allowed


# ----------------------------------------------------------------------------- CLI
def test_cli_exit_codes(budget_file, capsys: pytest.CaptureFixture[str]) -> None:
    path = str(budget_file())
    assert budget.main(["--hours", "3", "--budget", path]) == 0
    assert "Trong hạn mức" in capsys.readouterr().out
    assert budget.main(["--hours", "21", "--budget", path]) == 1
    assert "VƯỢT NGÂN SÁCH" in capsys.readouterr().out
    assert budget.main(["--hours", "1", "--api-vnd", "600000", "--budget", path, "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["allowed"] is False and payload["reasons"]
    assert budget.main(["--hours", "-1", "--budget", path]) == 2


def test_cli_record(budget_file, capsys: pytest.CaptureFixture[str]) -> None:
    path = budget_file()
    assert (
        budget.main(["--record", "--hours", "2", "--api-vnd", "1000", "--budget", str(path)]) == 0
    )
    assert "Đã ghi" in capsys.readouterr().out
    assert json.loads(path.read_text(encoding="utf-8"))["spent"] == {
        "gpu_hours": 2.0,
        "api_vnd": 1000,
    }
    assert budget.main(["--record", "--hours", "1", "--budget", str(path.parent / "x.json")]) == 2


def test_cli_requires_hours() -> None:
    with pytest.raises(SystemExit) as excinfo:
        budget.main([])
    assert excinfo.value.code == 2
