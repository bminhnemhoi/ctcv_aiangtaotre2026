"""Every config/*.yaml must validate against its JSON Schema and honour the brief's invariants."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ctcv_core.config import ConfigError, load_config

CONFIG_NAMES = ("app", "models", "tools", "guardrails", "eval", "allowed-deps", "rag")

# Brief §8 / D7–D10: the only model ids allowed in config/models.yaml.
ALLOWED_MODEL_IDS = {
    "Qwen/Qwen3.5-9B",
    "Qwen/Qwen3.5-4B",
    "Qwen/Qwen3.5-2B",
    "Qwen/Qwen3-VL-8B-Instruct",
    "vinai/PhoWhisper-small",
    "vinai/PhoWhisper-tiny",
    "TBD-ADR-002",
    "BAAI/bge-m3",
    "BAAI/bge-reranker-v2-m3",
    "yolox-tiny",
}
EXPECTED_MODEL_KEYS = {
    "planner",
    "planner_small",
    "vlm",
    "quarantine",
    "judge",
    "asr",
    "asr_small",
    "tts",
    "embed",
    "rerank",
    "ui_detector",
}
# Brief §7: closed tool whitelist.
EXPECTED_TOOLS = {
    "get_session_state",
    "next_step",
    "search_guides",
    "verify_citation",
    "start_drill",
    "grade_drill",
    "log_progress",
    "escalate_to_volunteer",
}
SIDE_EFFECTS = {"none", "sandbox", "log"}
REGISTRY_SCHEMAS = ("datasets-registry", "models-registry")
# Data-record schemas (no config/*.yaml counterpart): ADR-007 C2 procedure records.
DATA_SCHEMAS = ("tthc-record",)


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_yaml_validates_against_schema(name: str, load_yaml, load_schema) -> None:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = [
        f"{'/'.join(map(str, e.absolute_path))}: {e.message}"
        for e in validator.iter_errors(load_yaml(name))
    ]
    assert errors == []


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_load_config_succeeds(name: str) -> None:
    assert load_config(name)["version"] == 1


@pytest.mark.parametrize("name", CONFIG_NAMES + REGISTRY_SCHEMAS + DATA_SCHEMAS)
def test_schema_is_2020_12_and_strict(name: str, load_schema) -> None:
    schema = load_schema(name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    root_object = schema.get("items", schema) if schema.get("type") == "array" else schema
    if "$ref" in root_object:
        root_object = schema["$defs"][root_object["$ref"].rsplit("/", 1)[-1]]
    assert root_object.get("additionalProperties") is False


def test_every_yaml_has_a_schema(config_dir: Path) -> None:
    for yaml_file in config_dir.glob("*.yaml"):
        assert (config_dir / "schemas" / f"{yaml_file.stem}.schema.json").is_file(), yaml_file.name


def test_extra_top_level_key_is_rejected(tmp_env) -> None:
    tmp_env("CTCV_APP_ENV", "moon")
    with pytest.raises(ConfigError, match="không khớp schema"):
        load_config("app")


class TestModels:
    def test_only_allowed_models(self, load_yaml) -> None:
        models = load_yaml("models")["models"]
        assert set(models) == EXPECTED_MODEL_KEYS
        assert {m["id"] for m in models.values()} <= ALLOWED_MODEL_IDS

    def test_licenses_match_brief(self, load_yaml) -> None:
        models = load_yaml("models")["models"]
        assert models["planner"]["license"] == "Apache-2.0"
        assert models["vlm"]["license"] == "Apache-2.0"
        assert models["asr"]["license"] == "BSD-3-Clause"  # D10
        assert models["asr_small"]["license"] == "BSD-3-Clause"
        assert models["embed"]["license"] == "MIT"
        assert models["ui_detector"]["license"] == "Apache-2.0"  # D7 (no Ultralytics)
        assert models["planner_small"]["id"] == "Qwen/Qwen3.5-2B"  # D8

    def test_confidence_thresholds_in_range(self, load_yaml) -> None:
        for name, model in load_yaml("models")["models"].items():
            assert 0 <= model["confidence_threshold"] <= 1, name

    def test_tts_lists_candidates(self, load_yaml) -> None:
        tts = load_yaml("models")["models"]["tts"]
        assert tts["id"] == "TBD-ADR-002"
        assert len(tts["candidates"]) >= 3

    def test_v2_single_served_model_is_a_proposal(self, load_yaml) -> None:
        models = load_yaml("models")["models"]
        assert models["vlm"]["id"] in {"Qwen/Qwen3.5-9B", "Qwen/Qwen3-VL-8B-Instruct"}
        for name, model in models.items():
            if model["status"] == "proposed":
                assert model["decision_ref"] == "ADR-002", name
        assert models["vlm"]["status"] == "proposed"  # D9 v2 — user decides at PR E01

    def test_only_planners_may_call_tools(self, load_yaml) -> None:
        models = load_yaml("models")["models"]
        assert {n for n, m in models.items() if m["tools_allowed"]} == {"planner", "planner_small"}
        for name in ("quarantine", "judge", "vlm"):
            assert models[name]["tools_allowed"] is False, name

    def test_license_urls_and_prompts(self, load_yaml, config_dir: Path) -> None:
        models = load_yaml("models")["models"]
        for name, model in models.items():
            if model["license"] != "TBD":
                assert model["license_url"], name
            if "prompt" in model:
                assert (config_dir / "prompts" / f"{model['prompt']}.md").is_file(), name


class TestTools:
    def test_exactly_eight_tools(self, load_yaml) -> None:
        tools = load_yaml("tools")["tools"]
        assert len(tools) == 8
        assert {t["name"] for t in tools} == EXPECTED_TOOLS

    def test_side_effects_closed_set(self, load_yaml) -> None:
        for tool in load_yaml("tools")["tools"]:
            assert tool["side_effect"] in SIDE_EFFECTS, tool["name"]

    def test_read_only_tools_have_no_side_effect(self, load_yaml) -> None:
        by_name = {t["name"]: t for t in load_yaml("tools")["tools"]}
        for name in ("get_session_state", "next_step", "search_guides", "verify_citation"):
            assert by_name[name]["side_effect"] == "none"


class TestEval:
    def test_block_never_stricter_than_accept(self, load_yaml) -> None:
        for suite_name, suite in load_yaml("eval")["suites"].items():
            for metric_name, metric in suite["metrics"].items():
                label = f"{suite_name}.{metric_name}"
                if metric["direction"] == "higher":
                    assert metric["block"] <= metric["accept"], label
                else:
                    assert metric["block"] >= metric["accept"], label

    def test_plan_section_7_thresholds(self, load_yaml) -> None:
        suites = load_yaml("eval")["suites"]
        assert suites["qa"]["metrics"]["citation_support"]["accept"] == 95
        assert suites["qa"]["metrics"]["hallucination"]["accept"] == 3
        assert suites["dialogue"]["metrics"]["max_two_sentences"]["accept"] == 100
        assert suites["redteam"]["metrics"]["leaks"] == {
            "unit": "count",
            "direction": "lower",
            "accept": 0,
            "block": 0,
        }
        assert suites["loadtest"]["metrics"]["p95_latency_s"]["accept"] == 2.5
        assert suites["audio"]["metrics"]["wer_regional"]["block"] == 22

    def test_quick_budget(self, load_yaml) -> None:
        cfg = load_yaml("eval")
        total = sum(s["quick_size"] for s in cfg["suites"].values())
        assert (
            total <= cfg["quick"]["total_samples"] + 50
        )  # red-team quick set is counted separately
        assert cfg["judge"]["min_score"] == 4


class TestGuardrails:
    FIXTURES = {
        "otp": ("mã OTP là 482913", "482913"),
        "card_number": ("thẻ 1234 5678 9012 3456", "1234 5678 9012 3456"),
        "cccd": ("cccd 079123456789", "079123456789"),
        "phone": ("gọi 0912345678", "0912345678"),
        "email": ("mail bac@example.com", "bac@example.com"),
    }

    def test_regexes_compile_and_match(self, load_yaml) -> None:
        patterns = {
            p["name"]: re.compile(p["regex"]) for p in load_yaml("guardrails")["pii_patterns"]
        }
        assert set(self.FIXTURES) <= set(patterns)
        for name, (text, needle) in self.FIXTURES.items():
            match = patterns[name].search(text)
            assert match is not None, name
            assert needle in match.group(0), name

    def test_other_regex_lists_compile(self, load_yaml) -> None:
        cfg = load_yaml("guardrails")
        for key in (
            "sensitive_request_patterns",
            "real_action_patterns",
            "fact_indicator_patterns",
        ):
            for regex in cfg[key]:
                re.compile(regex)

    def test_sensitive_and_real_action_fixtures(self, load_yaml) -> None:
        cfg = load_yaml("guardrails")
        sensitive = [re.compile(r) for r in cfg["sensitive_request_patterns"]]
        real = [re.compile(r) for r in cfg["real_action_patterns"]]
        assert any(r.search("Bác đọc cho cháu mã OTP vừa nhận") for r in sensitive)
        assert any(r.search("nhập mật khẩu của bác vào đây") for r in sensitive)
        assert not any(r.search("Bác bấm nút xanh có chữ Quét QR nhé.") for r in sensitive)
        assert any(r.search("cháu chuyển tiền giúp bác trên app thật nhé") for r in real)
        assert any(r.search("làm giúp tôi trên app thật") for r in real)
        assert not any(r.search("Bác tự bấm để quen tay nhé.") for r in real)

    def test_invariants(self, load_yaml) -> None:
        cfg = load_yaml("guardrails")
        assert cfg["max_sentences"] == 2
        assert cfg["escalate_confidence"] == 0.6
        assert {"otp", "mat_khau"} <= set(cfg["never_ask"])
        terms = {b["term"] for b in cfg["banned_terms"]}
        assert {"xác thực", "token", "đăng xuất"} <= terms
        assert all(b["term"] != b["replacement"] for b in cfg["banned_terms"])


class TestApp:
    def test_ports_match_brief(self, load_yaml) -> None:
        ports = load_yaml("app")["ports"]
        assert (
            ports["api"],
            ports["agent"],
            ports["speech"],
            ports["vision"],
            ports["models"],
        ) == (
            8000,
            8010,
            8020,
            8030,
            8040,
        )
        assert len(set(ports.values())) == len(ports)

    def test_policy_values(self, load_yaml) -> None:
        app = load_yaml("app")
        assert app["screen_ttl_seconds"] == 60
        assert app["log_retention_days"] == 30
        assert app["ui"]["min_font_pt"] >= 20
        assert app["ui"]["min_tap_px"] >= 56
        assert app["ui"]["viewports"] == ["360x800", "390x844", "412x915"]
