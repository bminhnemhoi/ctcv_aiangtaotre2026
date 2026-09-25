"""Retrieval over the administrative-procedure (TTHC) knowledge base (ADR-007, DA940-01).

Submodules are imported explicitly to keep import side effects small:

* ``rag.types`` — procedure record (C2), chunk, hit, ``KnowledgeBase`` protocol, KB errors;
* ``rag.settings`` — :class:`RagSettings` resolved from ``config/rag.yaml`` + ``models.yaml``;
* ``rag.query`` — query normalisation, accent folding, tokens, synonym expansion;
* ``rag.chunker`` — deterministic record → chunk split (C3, ``tthc-chunk/1``);
* ``rag.fake`` — in-memory ``FakeKnowledgeBase`` for unit tests (no model, no network).

Nothing in this package is an agent tool; tools live in ``ctcv_agent.tools`` and only read
the knowledge base through ``GuideIndex``.
"""

__all__: list[str] = []
