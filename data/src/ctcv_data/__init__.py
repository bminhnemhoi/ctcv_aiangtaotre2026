"""ctcv-data: data pipeline steps (plan §7) and the dataset/model registry (brief §9).

Run a step with ``python -m ctcv_data.pipeline <step>``; ``python -m ctcv_data.pipeline``
runs every step in order (``make data``). E01 implements ``crawl`` (offline dry run)
and ``registry`` for real; the other steps report ``CHƯA HIỆN THỰC — E0X``.
"""

__all__: list[str] = []
