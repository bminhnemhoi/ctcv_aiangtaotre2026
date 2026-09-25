"""ctcv-drills: scam-vaccine drills at behaviour-pattern level (E01 brief §6, D27).

A drill (``drills/scenarios/*.json``) describes one scam situation with a single
labelled scammer turn, the red flags, 3–4 choices (exactly one safe) and a debrief.
:mod:`ctcv_drills.validator` blocks anything that looks like a copy-able script.
"""

from ctcv_drills.loader import checksum, list_drills, load_drill, variants_of
from ctcv_drills.rules import DrillRules, load_rules
from ctcv_drills.schema import (
    LABEL,
    SIMULATION_TAG,
    Channel,
    Drill,
    Impersonates,
    Option,
    RedFlag,
)
from ctcv_drills.scoring import Grade, grade, vulnerability_score
from ctcv_drills.validator import Issue, validate, validate_data, validate_file

__all__ = [
    "LABEL",
    "SIMULATION_TAG",
    "Channel",
    "Drill",
    "DrillRules",
    "Grade",
    "Impersonates",
    "Issue",
    "Option",
    "RedFlag",
    "checksum",
    "grade",
    "list_drills",
    "load_drill",
    "load_rules",
    "validate",
    "validate_data",
    "validate_file",
    "variants_of",
    "vulnerability_score",
]
