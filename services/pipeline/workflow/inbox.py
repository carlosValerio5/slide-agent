"""Async question inbox.

The designer can ask the user a question WITHOUT blocking the pipeline:
`ask_user` enqueues the question, returns the default immediately, and records
which slides depended on it so they can be re-designed once the user answers.
"""
from __future__ import annotations

import hashlib

from services.pipeline.graph.store import GraphStore
from services.shared.schemas import Question, QuestionStatus


def _qid(text: str) -> str:
    return "q_" + hashlib.sha256(text.encode()).hexdigest()[:10]


def ask_user(
    store: GraphStore,
    text: str,
    default: str,
    options: list[str] | None = None,
    affected_slide_ids: list[str] | None = None,
) -> str:
    """Enqueue a question (idempotent by text) and return the value to use now.

    If the user has already answered this question, the stored answer is used;
    otherwise the default is returned and the pipeline keeps running.
    """
    qid = _qid(text)
    existing = store.get_question(qid)
    if existing and existing.status == QuestionStatus.answered and existing.answer:
        return existing.answer

    q = existing or Question(
        id=qid,
        text=text,
        options=options or [],
        default=default,
        status=QuestionStatus.open,
    )
    # accumulate affected slides across design passes
    if affected_slide_ids:
        q.affected_slide_ids = sorted(
            set(q.affected_slide_ids) | set(affected_slide_ids)
        )
    store.upsert_question(q)
    return q.answer if (q.status == QuestionStatus.answered and q.answer) else default


def answer_question(store: GraphStore, qid: str, answer: str) -> Question | None:
    q = store.get_question(qid)
    if q is None:
        return None
    q.answer = answer
    q.status = QuestionStatus.answered
    store.upsert_question(q)
    return q
