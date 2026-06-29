"""Judge veracity/design enforcement and the async question inbox."""
import tempfile

from services.pipeline.graph import build_graph
from services.pipeline.graph.store import GraphStore
from services.pipeline.ingest import load_text
from services.pipeline.workflow import judge as judge_mod
from services.pipeline.workflow import run_pipeline
from services.pipeline.workflow.inbox import answer_question, ask_user
from services.shared.design_philosophy import DEFAULT_PHILOSOPHY
from services.shared.schemas import (
    Citation,
    ContentElement,
    Deck,
    QuestionStatus,
    Slide,
)


def _graph_store(text):
    store = GraphStore(tempfile.mktemp(suffix=".sqlite"))
    build_graph(store, [load_text("sample.md", text)], use_agent=False)
    return store


def test_judge_flags_fabricated_metric(sample_text):
    store = _graph_store(sample_text)
    bad_deck = Deck(
        title="X",
        slides=[
            Slide(id="title", layout="title", title="X"),
            Slide(
                id="s1",
                layout="bullets",
                title="Bogus",
                elements=[
                    ContentElement(id="e1", kind="bullet",
                                   text="Revenue grew by 999% last year", citations=[]),
                ],
            ),
        ],
    )
    verdict = judge_mod.judge(store, bad_deck, DEFAULT_PHILOSOPHY)
    assert verdict.decision == "revise"
    assert any(i.kind == "veracity" for i in verdict.issues)


def test_judge_flags_too_many_bullets(sample_text):
    store = _graph_store(sample_text)
    bullets = [
        ContentElement(id=f"e{i}", kind="bullet", text=f"point {i}", citations=[])
        for i in range(DEFAULT_PHILOSOPHY.max_bullets_per_slide + 3)
    ]
    deck = Deck(title="X", slides=[
        Slide(id="title", layout="title", title="X"),
        Slide(id="s1", layout="bullets", title="Too many", elements=bullets),
    ])
    verdict = judge_mod.judge(store, deck, DEFAULT_PHILOSOPHY)
    assert any(i.kind == "design" and "bullets" in i.message for i in verdict.issues)


def test_pipeline_deck_passes_judge(sample_text):
    store = GraphStore(tempfile.mktemp(suffix=".sqlite"))
    art = tempfile.mkdtemp()
    res = run_pipeline(store, [("sample.md", sample_text)], art, use_agent=False)
    assert res["ok"]
    assert res["verdict"]["decision"] == "pass"


def test_ask_user_is_nonblocking_and_answerable(tmp_store):
    # first call enqueues and returns the default
    val = ask_user(tmp_store, text="Audience?", default="general", options=["a", "b"])
    assert val == "general"
    qs = tmp_store.list_questions()
    assert len(qs) == 1 and qs[0].status == QuestionStatus.open

    # user answers -> subsequent calls return the answer
    answer_question(tmp_store, qs[0].id, "executives")
    val2 = ask_user(tmp_store, text="Audience?", default="general")
    assert val2 == "executives"
    assert tmp_store.list_questions()[0].status == QuestionStatus.answered
