"""Lazy wiring of the TTHC answer and intake services onto ``app.state`` (ADR-007 C6).

The first request that needs them loads the file knowledge base once, builds the answer
engine and the intake checker on that same KB, points the agent tools at it
(``wire_default_backends``) and keeps both services on ``app.state``. A failed build
(``KB_NOT_READY`` 503) is not cached, so the next request retries once the index exists.
Services already set on ``app.state`` (tests, custom deployments) are used as they are.

The engine, the index and the checker are imported inside functions: importing the API
never loads model clients, and unit tests never touch ``data/clean``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, Request

from ctcv_agent.contracts import AnswerService, IntakeService

if TYPE_CHECKING:
    from ctcv_agent.rag.settings import RagSettings
    from ctcv_agent.rag.types import KnowledgeBase

ANSWER_ATTR = "answer_service"
INTAKE_ATTR = "intake_service"
_BUILD_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class KnowledgeServices:
    """The two services built on one knowledge base."""

    answer: AnswerService
    intake: IntakeService


def load_file_knowledge_base(settings: RagSettings) -> KnowledgeBase:
    """Load the on-disk index (raises ``KB_NOT_READY``).

    The query embedder defaults to ``OllamaEmbedder(settings)``, created only once the index
    files passed their checks; no request is sent while loading.
    """
    from ctcv_agent.rag.index import FileKnowledgeBase

    return FileKnowledgeBase.load(settings)


def build_services(
    settings: RagSettings | None = None,
    *,
    kb: KnowledgeBase | None = None,
    composer: Any = None,
) -> KnowledgeServices:
    """Build the answer engine and the intake checker on one shared knowledge base.

    Args:
        settings: Resolved ``config/rag.yaml``; loaded when omitted.
        kb: Knowledge base to use; the file index is loaded when omitted.
        composer: Sentence composer for the engine; ``build_engine`` picks the configured
            one when omitted.

    Raises:
        KnowledgeBaseNotReady: the index is missing, stale or built with another model.
    """
    from ctcv_agent.ask import build_engine
    from ctcv_agent.intake import IntakeChecker
    from ctcv_agent.rag.index import wire_default_backends
    from ctcv_agent.rag.settings import load_rag_settings

    resolved = settings or load_rag_settings()
    base = kb if kb is not None else load_file_knowledge_base(resolved)
    engine = build_engine(resolved, kb=base, composer=composer)
    wire_default_backends(base)
    return KnowledgeServices(answer=engine, intake=IntakeChecker(base))


def _service(state: Any, attr: str) -> Any:
    """Return ``state.<attr>``, building both services under a lock the first time."""
    service = getattr(state, attr, None)
    if service is not None:
        return service
    with _BUILD_LOCK:
        service = getattr(state, attr, None)
        if service is None:
            built = build_services()
            if getattr(state, ANSWER_ATTR, None) is None:
                setattr(state, ANSWER_ATTR, built.answer)
            if getattr(state, INTAKE_ATTR, None) is None:
                setattr(state, INTAKE_ATTR, built.intake)
            service = getattr(state, attr)
    return service


def get_answer_service(request: Request) -> AnswerService:
    """FastAPI dependency: the citizen answer service (503 ``KB_NOT_READY`` if unbuilt)."""
    return _service(request.app.state, ANSWER_ATTR)


def get_intake_service(request: Request) -> IntakeService:
    """FastAPI dependency: the officer checklist service (503 ``KB_NOT_READY`` if unbuilt)."""
    return _service(request.app.state, INTAKE_ATTR)


AnswerServiceDep = Annotated[AnswerService, Depends(get_answer_service)]
IntakeServiceDep = Annotated[IntakeService, Depends(get_intake_service)]
