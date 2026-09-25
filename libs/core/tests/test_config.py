from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctcv_core.config import (
    ConfigError,
    clear_config_cache,
    config_path,
    find_repo_root,
    load_config,
    schema_path,
    validate_against_schema,
)

SIMPLE_SCHEMA = json.dumps(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["limit", "enabled", "ratio", "label"],
        "properties": {
            "limit": {"type": "integer", "minimum": 1},
            "enabled": {"type": "boolean"},
            "ratio": {"type": "number"},
            "label": {"type": "string"},
            "nested": {"type": "object"},
        },
    }
)
SIMPLE_YAML = "limit: 10\nenabled: false\nratio: 0.5\nlabel: xin chào\nnested: {a: 1}\n"


def write_config(root: Path, name: str, yaml_text: str, schema_json: str) -> None:
    (root / "config" / f"{name}.yaml").write_text(yaml_text, encoding="utf-8")
    (root / "config" / "schemas" / f"{name}.schema.json").write_text(schema_json, encoding="utf-8")


class TestFindRepoRoot:
    def test_finds_real_root(self) -> None:
        root = find_repo_root()
        assert (root / "pyproject.toml").is_file()
        assert (root / "config" / "app.yaml").is_file()

    def test_walks_up_from_nested_start(self, repo_root: Path) -> None:
        assert find_repo_root(repo_root / "libs" / "core" / "src") == repo_root

    def test_env_override(self, fake_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_REPO_ROOT", str(fake_root))
        assert find_repo_root() == fake_root.resolve()

    def test_env_override_invalid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_REPO_ROOT", str(tmp_path))
        with pytest.raises(ConfigError, match="không phải gốc kho mã"):
            find_repo_root()

    def test_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Không tìm thấy gốc kho mã"):
            find_repo_root(tmp_path)

    def test_member_pyproject_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
        with pytest.raises(ConfigError):
            find_repo_root(tmp_path)

    def test_broken_toml_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[[[", encoding="utf-8")
        with pytest.raises(ConfigError):
            find_repo_root(tmp_path)


class TestLoadConfig:
    @pytest.mark.parametrize("name", ["app", "models", "tools", "guardrails", "eval"])
    def test_real_configs_load(self, name: str) -> None:
        data = load_config(name)
        assert data["version"] == 1

    def test_paths(self, repo_root: Path) -> None:
        assert config_path("app") == repo_root / "config" / "app.yaml"
        assert schema_path("app") == repo_root / "config" / "schemas" / "app.schema.json"

    def test_returns_deep_copy(self) -> None:
        first = load_config("app")
        first["ports"]["api"] = 1
        assert load_config("app")["ports"]["api"] == 8000

    def test_cache_and_reload(self, fake_root: Path) -> None:
        write_config(fake_root, "simple", SIMPLE_YAML, SIMPLE_SCHEMA)
        assert load_config("simple", root=fake_root)["limit"] == 10
        (fake_root / "config" / "simple.yaml").write_text(
            SIMPLE_YAML.replace("limit: 10", "limit: 20"), encoding="utf-8"
        )
        assert load_config("simple", root=fake_root)["limit"] == 10
        assert load_config("simple", root=fake_root, reload=True)["limit"] == 20
        clear_config_cache()
        assert load_config("simple", root=fake_root)["limit"] == 20

    def test_schema_rejection(self, fake_root: Path) -> None:
        write_config(fake_root, "simple", "limit: 0\nenabled: x\n", SIMPLE_SCHEMA)
        with pytest.raises(ConfigError) as info:
            load_config("simple", root=fake_root)
        assert "không khớp schema" in info.value.message_vi
        assert info.value.status == 500
        assert info.value.details is not None
        assert len(info.value.details["errors"]) >= 3

    def test_missing_file(self, fake_root: Path) -> None:
        with pytest.raises(ConfigError, match="Thiếu file cấu hình"):
            load_config("nope", root=fake_root)

    def test_missing_schema(self, fake_root: Path) -> None:
        (fake_root / "config" / "simple.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
        with pytest.raises(ConfigError, match="Thiếu JSON Schema"):
            load_config("simple", root=fake_root)

    def test_invalid_yaml(self, fake_root: Path) -> None:
        write_config(fake_root, "simple", "a: [1,\n", SIMPLE_SCHEMA)
        with pytest.raises(ConfigError, match="sai cú pháp YAML"):
            load_config("simple", root=fake_root)

    def test_non_mapping_yaml(self, fake_root: Path) -> None:
        write_config(fake_root, "simple", "- 1\n- 2\n", SIMPLE_SCHEMA)
        with pytest.raises(ConfigError, match="bảng khóa–giá trị"):
            load_config("simple", root=fake_root)

    def test_invalid_schema_json(self, fake_root: Path) -> None:
        write_config(fake_root, "simple", SIMPLE_YAML, "{not json")
        with pytest.raises(ConfigError, match="không phải JSON hợp lệ"):
            load_config("simple", root=fake_root)

    def test_many_errors_are_truncated(self, fake_root: Path) -> None:
        schema = json.dumps(
            {
                "type": "object",
                "properties": {f"k{i}": {"type": "integer"} for i in range(8)},
            }
        )
        yaml_text = "".join(f"k{i}: x\n" for i in range(8))
        write_config(fake_root, "many", yaml_text, schema)
        with pytest.raises(ConfigError, match=r"và 3 lỗi khác"):
            load_config("many", root=fake_root)


class TestEnvOverrides:
    @pytest.fixture(autouse=True)
    def _simple(self, fake_root: Path) -> None:
        write_config(fake_root, "simple", SIMPLE_YAML, SIMPLE_SCHEMA)
        self.root = fake_root

    def test_int_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_LIMIT", "42")
        assert load_config("simple", root=self.root)["limit"] == 42

    def test_bool_and_float_and_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_ENABLED", "true")
        monkeypatch.setenv("CTCV_SIMPLE_RATIO", "0.75")
        monkeypatch.setenv("CTCV_SIMPLE_LABEL", "tạm biệt")
        data = load_config("simple", root=self.root)
        assert data["enabled"] is True
        assert data["ratio"] == 0.75
        assert data["label"] == "tạm biệt"

    @pytest.mark.parametrize("word", ["0", "no", "off", "false", "không"])
    def test_bool_false_words(self, monkeypatch: pytest.MonkeyPatch, word: str) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_ENABLED", word)
        assert load_config("simple", root=self.root)["enabled"] is False

    def test_bad_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_LIMIT", "nhiều")
        with pytest.raises(ConfigError, match="số nguyên"):
            load_config("simple", root=self.root)

    def test_bad_bool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_ENABLED", "maybe")
        with pytest.raises(ConfigError, match="true/false"):
            load_config("simple", root=self.root)

    def test_bad_float(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_RATIO", "x")
        with pytest.raises(ConfigError, match="số thực"):
            load_config("simple", root=self.root)

    def test_override_validated_by_schema(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_LIMIT", "0")
        with pytest.raises(ConfigError, match="không khớp schema"):
            load_config("simple", root=self.root)

    def test_non_scalar_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_NESTED", "{}")
        with pytest.raises(ConfigError, match="không phải giá trị vô hướng"):
            load_config("simple", root=self.root)

    def test_unknown_key_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_SIMPLE_UNKNOWN", "1")
        assert "unknown" not in load_config("simple", root=self.root)

    def test_other_config_prefix_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTCV_OTHER_LIMIT", "99")
        assert load_config("simple", root=self.root)["limit"] == 10


def test_validate_against_schema_ok() -> None:
    validate_against_schema({"a": 1}, {"type": "object"}, "x")


def test_validate_against_schema_error_location() -> None:
    schema = {
        "type": "object",
        "properties": {"a": {"type": "object", "properties": {"b": {"type": "integer"}}}},
    }
    with pytest.raises(ConfigError, match="a/b:"):
        validate_against_schema({"a": {"b": "x"}}, schema, "x")
