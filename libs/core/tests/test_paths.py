from __future__ import annotations

from pathlib import Path

from ctcv_core import paths


def test_repo_root_is_workspace_root() -> None:
    assert (paths.REPO_ROOT / "pyproject.toml").is_file()
    assert (paths.REPO_ROOT / "uv.lock").is_file()


def test_config_paths_exist() -> None:
    assert paths.CONFIG_DIR.is_dir()
    assert paths.SCHEMAS_DIR.is_dir()
    assert paths.PROMPTS_DIR.is_dir()
    assert (paths.PROMPTS_DIR / "coach.v1.md").is_file()


def test_all_paths_are_under_root() -> None:
    for name in paths.__all__:
        value = getattr(paths, name)
        assert isinstance(value, Path)
        assert value == paths.REPO_ROOT or paths.REPO_ROOT in value.parents


def test_expected_layout() -> None:
    assert paths.SCENARIOS_DIR == paths.REPO_ROOT / "sandbox" / "scenarios"
    assert paths.DRILLS_DIR == paths.REPO_ROOT / "drills" / "scenarios"
    assert paths.REGISTRY_DIR == paths.REPO_ROOT / "data" / "registry"
    assert paths.PROMPT_LOG_DIR == paths.REPO_ROOT / "docs" / "prompt-log"
