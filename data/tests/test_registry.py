"""Registry validation: good and bad fixtures, hash computation, REPORT.md, real registry."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ctcv_data.registry import (
    HashCheck,
    check_hashes,
    load_registry,
    run_registry,
    sha256_of_path,
    update_sha256,
    validate_entries,
)


def test_good_fixture_validates(fake_repo: Path, good_registry: Path) -> None:
    result = run_registry(fake_repo, good_registry)
    assert result.ok, result.problems
    assert [d["name"] for d in result.datasets] == ["guides-fixture", "tiny-eval", "nc-audio"]
    assert len(result.models) == 2
    assert result.report_path == good_registry / "REPORT.md"
    report = result.report_path.read_text(encoding="utf-8")
    assert "HỢP LỆ" in report and "tiny-eval" in report


def test_dates_are_normalised_to_strings(good_registry: Path) -> None:
    entries = load_registry("datasets", good_registry)
    assert entries[1]["collected_at"] == "2026-09-18"  # unquoted YAML date
    assert entries[0]["tos_checked_on"] == "2026-09-18"


def test_bad_fixture_lists_every_problem(fake_repo: Path, bad_registry: Path) -> None:
    result = run_registry(fake_repo, bad_registry, write_report=False)
    assert not result.ok
    joined = "\n".join(result.problems)
    for needle in (
        "name",  # pattern
        "source_type",  # synthetic source with official type
        "sha256",
        "used_for",
        "pii",
        "size/records",
        "extra_field",
        "tên trùng 'nc-but-redistributed'",
        "license",  # AGPL not in SPDX enum of models
        "quantization",
        "served_at",
    ):
        assert needle in joined, needle


def test_cross_entry_rules(fake_repo: Path) -> None:
    entries = [
        {
            "name": "nc-set",
            "version": "1.0",
            "source": "https://example.org/",
            "source_type": "open_dataset",
            "license": "CC-BY-NC-4.0",
            "redistribute": False,
            "derived_from": ["missing-parent"],
            "tos_url": "https://example.org/",
            "tos_checked_on": None,
            "collected_at": "2026-09-18",
            "size": {"records": 0, "mb": 0},
            "sha256": "pending",
            "used_for": ["eval"],
            "pii": "none",
            "eval_only": True,
        }
    ]
    problems = validate_entries("datasets", entries, fake_repo)
    assert any("derived_from" in p and "missing-parent" in p for p in problems)
    entries[0]["derived_from"] = []
    assert validate_entries("datasets", entries, fake_repo) == []


def test_sha256_of_file_and_directory(tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_bytes(b"ctcv")
    assert sha256_of_path(file) == hashlib.sha256(b"ctcv").hexdigest()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_bytes(b"x")
    first = sha256_of_path(tmp_path)
    (tmp_path / "sub" / "b.txt").write_bytes(b"y")
    assert sha256_of_path(tmp_path) != first


def test_check_hashes_statuses(fake_repo: Path, good_registry: Path) -> None:
    entries = load_registry("datasets", good_registry)
    checks = {c.name: c for c in check_hashes(entries, fake_repo)}
    assert checks["tiny-eval"].status == "pending" and checks["tiny-eval"].computed
    assert checks["guides-fixture"].status == "missing"
    assert checks["nc-audio"].status == "no_path"
    entries[1]["sha256"] = "0" * 64
    mismatch = check_hashes(entries, fake_repo)[1]
    assert isinstance(mismatch, HashCheck) and mismatch.status == "mismatch"


def test_update_hashes_writes_back_and_keeps_comments(fake_repo: Path, good_registry: Path) -> None:
    result = run_registry(fake_repo, good_registry, update_hashes=True)
    assert result.ok
    text = (good_registry / "datasets.yaml").read_text(encoding="utf-8")
    assert text.startswith("# Valid fixture")
    computed = sha256_of_path(fake_repo / "eval" / "sets" / "tiny.jsonl")
    assert f"sha256: {computed}" in text
    assert not update_sha256(good_registry / "datasets.yaml", "tiny-eval", computed)  # unchanged
    again = run_registry(fake_repo, good_registry, write_report=False)
    assert {c.name: c.status for c in again.hash_checks}["tiny-eval"] == "match"


def test_mismatch_is_an_error(fake_repo: Path, good_registry: Path) -> None:
    update_sha256(good_registry / "datasets.yaml", "tiny-eval", "f" * 64)
    result = run_registry(fake_repo, good_registry, write_report=False)
    assert not result.ok
    assert any("sha256 khai báo khác" in p for p in result.problems)


class TestRealRegistry:
    def test_real_registry_is_valid(self, repo_root: Path, tmp_path: Path) -> None:
        result = run_registry(repo_root, write_report=False)
        assert result.ok, result.problems

    def test_licences_match_brief(self, repo_root: Path) -> None:
        models = {m["name"]: m for m in load_registry("models", repo_root / "data" / "registry")}
        assert models["asr-phowhisper-small"]["license"] == "BSD-3-Clause"  # D10
        assert models["asr-phowhisper-tiny"]["license"] == "BSD-3-Clause"
        assert models["ui-detector-yolox-tiny"]["license"] == "Apache-2.0"  # D7
        assert models["planner-small-base"]["base"] == "Qwen/Qwen3.5-2B"  # D8
        assert models["embed-bge-m3"]["license"] == "MIT"
        for model in models.values():
            assert model["license_url"] and "card" in model

    def test_vivos_is_eval_only(self, repo_root: Path) -> None:
        datasets = {
            d["name"]: d for d in load_registry("datasets", repo_root / "data" / "registry")
        }
        vivos = datasets["vivos"]
        assert vivos["license"] == "CC-BY-NC-SA-4.0"
        assert vivos["eval_only"] is True and vivos["redistribute"] is False
        assert vivos["used_for"] == ["eval"]
        assert datasets["common-voice-vi"]["license"] == "CC0-1.0"
        assert datasets["guides-official"]["redistribute"] is False
        for entry in datasets.values():
            for key in ("redistribute", "derived_from", "source_type", "tos_checked_on", "path"):
                assert key in entry, (entry["name"], key)
            if entry["source"] == "synthetic":
                for key in ("generator_model", "generator_license", "tos_url"):
                    assert entry[key], (entry["name"], key)
