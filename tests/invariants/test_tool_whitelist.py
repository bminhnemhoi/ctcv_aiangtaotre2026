"""Invariant (a), brief §7/§15: the tool set is closed and its side effects are bounded.

* every registered tool is declared in ``config/tools.yaml`` with the same side effect;
* side effects are only ``none``, ``sandbox`` or ``log``;
* no module under ``ctcv_agent.tools`` imports a network or process library or calls
  ``os.system``-like functions;
* nothing under ``services/agent/src`` defines a function, class or module named like
  ``send_money``, ``transfer``, ``sms`` or ``payment``;
* no tool takes ``user_id`` as an argument (brief D28) and every ``Input`` forbids extras.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import MappingProxyType

import pytest

import ctcv_agent
import ctcv_agent.tools as tools_pkg
from ctcv_agent.schemas import SIDE_EFFECTS
from ctcv_agent.tools.registry import TOOL_REGISTRY
from ctcv_agent.tools.router import ToolNotAllowed, allowed_tools, resolve
from ctcv_core.config import load_config

TOOLS_DIR = Path(tools_pkg.__file__).resolve().parent
AGENT_SRC = Path(ctcv_agent.__file__).resolve().parent
FORBIDDEN_IMPORTS = frozenset(
    {
        "httpx",
        "requests",
        "subprocess",
        "socket",
        "urllib",
        "http",
        "aiohttp",
        "smtplib",
        "ftplib",
        "telnetlib",
        "xmlrpc",
        "multiprocessing",
        "ctypes",
    }
)
FORBIDDEN_OS_ATTR_RE = re.compile(
    r"^(?:system|popen\w*|exec\w*|spawn\w*|fork\w*|startfile|kill\w*)$"
)
FORBIDDEN_NAME_RE = re.compile(r"send_money|transfer|sms|payment", re.IGNORECASE)


def _tool_modules() -> list[Path]:
    return sorted(TOOLS_DIR.glob("*.py"))


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _os_calls(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and FORBIDDEN_OS_ATTR_RE.match(node.attr)
        ):
            found.append(f"os.{node.attr}")
    return found


def test_registry_is_a_read_only_mapping() -> None:
    assert isinstance(TOOL_REGISTRY, MappingProxyType)
    with pytest.raises(TypeError):
        TOOL_REGISTRY["send_money"] = None  # type: ignore[index]


def test_registry_is_subset_of_config_whitelist() -> None:
    declared = set(allowed_tools())
    missing = set(TOOL_REGISTRY) - declared
    assert not missing, f"tool trong registry nhưng không có trong config/tools.yaml: {missing}"


def test_config_whitelist_equals_registry() -> None:
    names = [entry["name"] for entry in load_config("tools")["tools"]]
    assert len(names) == len(set(names)), "config/tools.yaml có tên tool trùng"
    assert set(names) == set(TOOL_REGISTRY)


def test_side_effects_are_bounded_and_agree_with_config() -> None:
    declared = allowed_tools()
    assert SIDE_EFFECTS == {"none", "sandbox", "log"}
    for name, spec in TOOL_REGISTRY.items():
        assert spec.side_effect in SIDE_EFFECTS, name
        assert spec.side_effect == declared[name]["side_effect"], name


@pytest.mark.parametrize("path", _tool_modules(), ids=lambda p: p.name)
def test_tool_module_has_no_network_or_process_imports(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bad = _imported_roots(tree) & FORBIDDEN_IMPORTS
    assert not bad, f"{path.name} import thư viện cấm: {sorted(bad)}"
    assert not _os_calls(tree), f"{path.name} gọi hàm tiến trình của os"


def test_no_money_or_messaging_function_names_in_agent_source() -> None:
    offenders: list[str] = []
    for path in sorted(AGENT_SRC.rglob("*.py")):
        if FORBIDDEN_NAME_RE.search(path.stem):
            offenders.append(f"{path.relative_to(AGENT_SRC)} (tên module)")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if FORBIDDEN_NAME_RE.search(node.name):
                    offenders.append(f"{path.relative_to(AGENT_SRC)}:{node.lineno} {node.name}")
    assert not offenders, "\n".join(offenders)


def test_no_tool_takes_user_id_and_inputs_forbid_extras() -> None:
    for name, spec in TOOL_REGISTRY.items():
        assert "user_id" not in spec.input_model.model_fields, f"{name} nhận user_id (D28)"
        assert spec.input_model.model_config.get("extra") == "forbid", name
        assert spec.output_model.model_config.get("extra") == "forbid", name


@pytest.mark.parametrize(
    "name", ["send_money", "transfer", "send_sms", "payment", "__import__", "next_step "]
)
def test_router_refuses_names_outside_the_whitelist(name: str) -> None:
    with pytest.raises(ToolNotAllowed) as exc:
        resolve(name)
    assert exc.value.code == "TOOL_NOT_ALLOWED" and exc.value.status == 403
