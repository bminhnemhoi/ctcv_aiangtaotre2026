"""Every system prompt in config/prompts has versioned YAML front matter and the coach rules."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from ctcv_core.text import contains_banned_terms

EXPECTED_PROMPTS = {"coach", "quarantine", "vlm_screen", "judge", "tthc_ask"}
FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)


def _split(path: Path) -> tuple[dict, str]:
    match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    assert match, f"{path.name}: thiếu YAML front matter"
    meta = yaml.safe_load(match.group(1))
    assert isinstance(meta, dict)
    return meta, match.group(2)


@pytest.fixture(scope="module")
def prompt_files(config_dir: Path) -> dict[str, Path]:
    files = {p.name.split(".")[0]: p for p in (config_dir / "prompts").glob("*.v*.md")}
    assert set(files) == EXPECTED_PROMPTS
    return files


def test_filenames_carry_version(prompt_files: dict[str, Path]) -> None:
    for path in prompt_files.values():
        assert re.fullmatch(r"[a-z_]+\.v\d+\.md", path.name), path.name


@pytest.mark.parametrize("name", sorted(EXPECTED_PROMPTS))
def test_front_matter(name: str, prompt_files: dict[str, Path], load_yaml) -> None:
    meta, body = _split(prompt_files[name])
    assert isinstance(meta["version"], int) and meta["version"] >= 1
    assert f".v{meta['version']}." in prompt_files[name].name
    assert meta["model"] in load_yaml("models")["models"], (
        "model phải là khóa trong config/models.yaml"
    )
    assert meta["purpose"].strip()
    assert len(body.strip()) > 200


def test_coach_prompt_rules(prompt_files: dict[str, Path]) -> None:
    _, body = _split(prompt_files["coach"])
    for needle in ("2 câu", "OTP", "mật khẩu", "nguồn", "xác nhận ý định", "mô phỏng", "màu"):
        assert needle in body, needle
    assert "PlannerOutput" in body


def test_coach_prompt_uses_no_banned_terms_outside_rule_list(
    prompt_files: dict[str, Path], load_yaml
) -> None:
    _, body = _split(prompt_files["coach"])
    example_lines = [
        line
        for line in body.splitlines()
        if line.startswith(("Lượt đầu", "Sau khi", "Bấm nhầm", "Hỏi về"))
    ]
    banned = [b["term"] for b in load_yaml("guardrails")["banned_terms"]]
    for line in example_lines:
        for term in banned:
            assert not re.search(rf"(?<!\w){re.escape(term)}(?!\w)", line, re.IGNORECASE), (
                term,
                line,
            )


def test_vlm_prompt_json_spec(prompt_files: dict[str, Path]) -> None:
    meta, body = _split(prompt_files["vlm_screen"])
    assert meta["model"] == "vlm"
    for key in ("app_guess", "screen_title", "elements", "sensitive_regions", "next_step_hint"):
        assert f'"{key}"' in body, key


def test_judge_prompt_rubric(prompt_files: dict[str, Path], load_yaml) -> None:
    meta, body = _split(prompt_files["judge"])
    assert meta["scale"] == 5
    assert meta["min_score"] == load_yaml("eval")["judge"]["min_score"]
    for needle in (
        "| 5 |",
        "| 4 |",
        "| 3 |",
        "| 2 |",
        "| 1 |",
        "two_sentences",
        "concrete_action",
        "intent_confirmed",
    ):
        assert needle in body, needle


def test_quarantine_prompt_treats_input_as_data(prompt_files: dict[str, Path]) -> None:
    meta, body = _split(prompt_files["quarantine"])
    assert meta["tools"] == "none"
    assert "<<<UNTRUSTED>>>" in body
    assert "red_flags" in body


def test_tthc_ask_prompt_rules(prompt_files: dict[str, Path]) -> None:
    meta, body = _split(prompt_files["tthc_ask"])
    for needle in ("KHONG_CHAC", "doc_ids", "NGUON", "OTP", "1 câu"):
        assert needle in body, needle
    assert meta["model"] == "planner_small"
    assert meta["tools"] == "none"


def test_tthc_ask_prompt_lists_every_banned_term(prompt_files: dict[str, Path], load_yaml) -> None:
    _, body = _split(prompt_files["tthc_ask"])
    missing = [b["term"] for b in load_yaml("guardrails")["banned_terms"] if b["term"] not in body]
    assert missing == [], "tthc_ask.v1.md phải liệt kê đủ banned_terms"


def test_tthc_ask_prompt_examples_follow_the_rules(
    prompt_files: dict[str, Path], load_yaml
) -> None:
    _, body = _split(prompt_files["tthc_ask"])
    outputs = [json.loads(line) for line in body.splitlines() if line.startswith('{"answer"')]
    assert len(outputs) >= 3  # format spec + 2 examples
    for out in outputs:
        assert set(out) == {"answer", "doc_ids"}
    answers = [o["answer"] for o in outputs[1:]]
    assert "KHONG_CHAC" in answers
    assert any(re.search(r"\d", a) for a in answers), "cần 1 ví dụ có số khớp NGUỒN"
    banned = [b["term"] for b in load_yaml("guardrails")["banned_terms"]]
    for answer in answers:
        assert len(answer.split()) <= 40, answer
        assert contains_banned_terms(answer, banned) == [], answer
