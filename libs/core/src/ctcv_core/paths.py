"""Well-known repository paths, resolved once from the uv workspace root."""

from ctcv_core.config import find_repo_root

REPO_ROOT = find_repo_root()
CONFIG_DIR = REPO_ROOT / "config"
SCHEMAS_DIR = CONFIG_DIR / "schemas"
PROMPTS_DIR = CONFIG_DIR / "prompts"
SCENARIOS_DIR = REPO_ROOT / "sandbox" / "scenarios"
DRILLS_DIR = REPO_ROOT / "drills" / "scenarios"
REGISTRY_DIR = REPO_ROOT / "data" / "registry"
DOCS_DIR = REPO_ROOT / "docs"
STATUS_DIR = DOCS_DIR / "status"
PROMPT_LOG_DIR = DOCS_DIR / "prompt-log"
DOSSIER_OUT_DIR = DOCS_DIR / "dossier" / "out"

__all__ = [
    "CONFIG_DIR",
    "DOCS_DIR",
    "DOSSIER_OUT_DIR",
    "DRILLS_DIR",
    "PROMPTS_DIR",
    "PROMPT_LOG_DIR",
    "REGISTRY_DIR",
    "REPO_ROOT",
    "SCENARIOS_DIR",
    "SCHEMAS_DIR",
    "STATUS_DIR",
]
