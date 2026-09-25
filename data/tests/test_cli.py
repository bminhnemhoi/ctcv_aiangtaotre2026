"""`python -m ctcv_data.pipeline` exit codes and step behaviour."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ctcv_data.manifest import read_manifest
from ctcv_data.pipeline import STEP_ORDER, PipelineConfig, StepReport, get_step, run_steps
from ctcv_data.pipeline.__main__ import main


def test_list_steps(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for name in STEP_ORDER:
        assert name in out


def test_unknown_step_is_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["fly_to_moon"])
    assert excinfo.value.code == 2


# normalize (P1), chunk_embed (P2b) and build_eval_sets (P6) are implemented by ADR-007 and have
# their own tests (test_normalize.py, ...); they no longer report "CHƯA HIỆN THỰC".
IMPLEMENTED_STEPS = {"crawl", "registry", "normalize", "chunk_embed", "build_eval_sets"}


@pytest.mark.parametrize("step", [s for s in STEP_ORDER if s not in IMPLEMENTED_STEPS])
def test_unimplemented_steps_exit_zero(step: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([step]) == 0
    out = capsys.readouterr().out
    assert "CHƯA HIỆN THỰC" in out and step in out
    report = get_step(step)(PipelineConfig())
    assert report.status == "skipped" and report.exit_code == 0
    assert report.details["epic"].startswith("E")


def test_crawl_dry_run_writes_manifest_skeleton(
    repo_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["crawl", "--raw-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "[OK] crawl" in out and "offline" in out
    entries = read_manifest(tmp_path / "guides" / "manifest.jsonl")
    assert entries and all(e.status == "pending" and e.robots == {} for e in entries)
    assert all(e.url.startswith("https://") for e in entries)


def test_crawl_fails_on_bad_sources(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[tool.uv.workspace]\nmembers=[]\n", encoding="utf-8")
    (root / "data" / "sources.yaml").write_text(
        "crawl_rules: {rate_limit_rps: 1, respect_robots: true}\nallowlist: []\nsources: []\n",
        encoding="utf-8",
    )
    assert main(["crawl", "--root", str(root), "--raw-dir", str(tmp_path / "raw")]) == 1
    assert "[LỖI] crawl" in capsys.readouterr().out


def test_registry_step_ok_and_report(repo_root: Path, tmp_path: Path, capsys) -> None:
    registry = tmp_path / "registry"
    shutil.copytree(
        repo_root / "data" / "registry", registry, ignore=shutil.ignore_patterns("REPORT.md")
    )
    assert main(["registry", "--registry-dir", str(registry)]) == 0
    assert "[OK] registry" in capsys.readouterr().out
    assert (registry / "REPORT.md").is_file()


def test_registry_step_fails_on_invalid(fake_repo: Path, bad_registry: Path, capsys) -> None:
    assert main(["registry", "--root", str(fake_repo), "--registry-dir", str(bad_registry)]) == 1
    assert "[LỖI] registry" in capsys.readouterr().out


def test_run_steps_stops_after_failure(fake_repo: Path, bad_registry: Path) -> None:
    cfg = PipelineConfig(root=fake_repo, registry_dir=bad_registry, raw_dir=fake_repo / "raw")
    reports = run_steps(["registry", "normalize"], cfg)
    assert [r.status for r in reports] == ["failed"]
    assert isinstance(reports[0], StepReport)


def test_all_steps_run_in_order(repo_root: Path, tmp_path: Path, capsys) -> None:
    registry = tmp_path / "registry"
    shutil.copytree(
        repo_root / "data" / "registry", registry, ignore=shutil.ignore_patterns("REPORT.md")
    )
    argv = ["--raw-dir", str(tmp_path / "raw"), "--registry-dir", str(registry)]
    assert main([*argv, "--clean-dir", str(tmp_path / "clean")]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("[")]
    assert [ln.split("] ")[1].split(":")[0] for ln in lines] == list(STEP_ORDER)


def test_registry_declares_tthc_bca_v1(repo_root: Path) -> None:
    import re

    import yaml

    entries = yaml.safe_load((repo_root / "data/registry/datasets.yaml").read_text("utf-8"))
    entry = next(e for e in entries if e["name"] == "tthc-bca-v1")
    assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
    assert entry["path"] == "data/raw/tthc/manifest.jsonl" and entry["size"]["records"] >= 50
    assert entry["redistribute"] is False and entry["pii"] == "none"
    assert entry["used_for"] == ["rag", "eval"] and entry["source_type"] == "co_quan_nha_nuoc"
    assert entry["tos_checked_on"] is None and entry["generator_model"] is None
    ignored = (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/raw/*" in ignored and "data/clean/*" in ignored
