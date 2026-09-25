"""ctcv-training: the fine-tuning runbook of CTCV (plan §7 ``make train``).

E01 ships the parts that need no GPU: the training configs in ``training/configs``
(validated by ``training/configs/schema.json``), the budget gate
(:mod:`ctcv_training.budget`, stdlib only so the Claude Code hook can use it) and the
run-directory convention (:mod:`ctcv_training.runs`). The trainers (SFT, DPO, quantize,
YOLOX, ASR LoRA) land in E07/E08; ``make train`` prints ``CHƯA HIỆN THỰC — E07`` until then.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
