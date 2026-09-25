from __future__ import annotations

import json
from pathlib import Path

import declaration
import pytest

MODELS_REGISTRY = """
- name: planner-lora-v1
  base: Qwen/Qwen3.5-9B
  license: Apache-2.0
  license_url: https://huggingface.co/Qwen/Qwen3.5-9B
  adapter_path: training/runs/2026-10-01-sft/adapter
  quantization: awq
  eval_report: null
  served_at: null
  card: null
"""
DATASETS_REGISTRY = """
- name: coach-dialogues
  version: "1.0"
  source: synthetic
  source_type: synthetic
  license: CC-BY-4.0
  redistribute: true
  collected_at: 2026-10-01
  size: {records: 8000, mb: 12}
  sha256: pending
  used_for: [sft]
  pii: none
  generator_model: Qwen/Qwen3.5-9B
  generator_license: Apache-2.0
- name: common-voice-vi
  version: "17.0"
  source: https://commonvoice.mozilla.org/vi
  source_type: public-dataset
  license: CC0-1.0
  redistribute: false
  collected_at: 2026-10-01
  size: {records: 1000, mb: 500}
  sha256: pending
  used_for: [eval]
  pii: none
  tos_url: https://commonvoice.mozilla.org/terms
  tos_checked_on: 2026-10-01
"""


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    (tmp_path / "data" / "registry").mkdir(parents=True)
    (tmp_path / "data" / "registry" / "models.yaml").write_text(MODELS_REGISTRY, encoding="utf-8")
    (tmp_path / "data" / "registry" / "datasets.yaml").write_text(
        DATASETS_REGISTRY, encoding="utf-8"
    )
    (tmp_path / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "pyyaml"\nversion = "6.0.3"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        '[[package]]\nname = "ctcv-core"\nversion = "0.1.0"\nsource = { editable = "libs/core" }\n',
        encoding="utf-8",
    )
    (tmp_path / "apps" / "web").mkdir(parents=True)
    (tmp_path / "apps" / "web" / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.3.1"}, "devDependencies": {"vite": "^5"}}),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "prompt-log").mkdir(parents=True)
    (tmp_path / "docs" / "prompt-log" / "INDEX.md").write_text(
        "| ts | file | sha256 |\n| --- | --- | --- |\n| t | a.jsonl | " + "a" * 64 + " |\n",
        encoding="utf-8",
    )
    for folder in ("sandbox", "services/agent", "libs/core"):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_full_declaration(fake_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert declaration.main(["--root", str(fake_repo)]) == 0
    out_file = fake_repo / "docs" / "dossier" / "out" / "06_KeKhaiAI.md"
    text = out_file.read_text(encoding="utf-8")
    for heading in ("## 1. Đội tự xây", "## 2. AI hỗ trợ", "## 3. Kế thừa mã nguồn mở"):
        assert heading in text
    assert "planner-lora-v1" in text and "coach-dialogues" in text and "common-voice-vi" in text
    assert "| pyyaml | 6.0.3 | PyPI |" in text
    assert "ctcv-core" not in text.split("### 3.3")[1]
    assert "| react | ^18.3.1 | dependencies |" in text
    assert "1 phiên có hash" in text
    assert "| sandbox |" in text and "| deploy |" not in text
    assert "LƯU Ý" not in capsys.readouterr().out


def test_missing_inputs_are_tolerated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "models.yaml").write_text(
        "version: 1\nmodels:\n  planner: {id: Qwen/Qwen3.5-9B, license: Apache-2.0, kind: llm}\n",
        encoding="utf-8",
    )
    assert declaration.main(["--root", str(tmp_path), "--out", str(tmp_path / "k.md")]) == 0
    text = (tmp_path / "k.md").read_text(encoding="utf-8")
    assert "| planner | Qwen/Qwen3.5-9B | Apache-2.0 |" in text  # fallback to config/models.yaml
    assert "_(chưa có mục nào)_" in text
    notes = capsys.readouterr().out
    assert "uv.lock" in notes and "datasets.yaml" in notes and "apps/web" in notes


def test_registry_must_be_a_list(tmp_path: Path) -> None:
    (tmp_path / "data" / "registry").mkdir(parents=True)
    (tmp_path / "data" / "registry" / "models.yaml").write_text("a: 1\n", encoding="utf-8")
    notes: list[str] = []
    assert declaration.load_registry(tmp_path, "models", notes) == []
    assert notes and "không phải danh sách" in notes[0]


def test_real_repo_runs(tmp_path: Path) -> None:
    out = tmp_path / "06.md"
    assert declaration.main(["--root", str(declaration.REPO_ROOT), "--out", str(out)]) == 0
    assert "Claude Code" in out.read_text(encoding="utf-8")
