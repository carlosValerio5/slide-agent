"""FastAPI app: upload -> build -> SSE progress -> question inbox -> deck.

Local single-user MVP. Each project gets a directory under DATA_DIR with its
uploaded files, one SQLite db, and rendered artifacts. The build runs in a
background thread; progress is streamed via Server-Sent Events sourced from the
project's run_state row.
"""
from __future__ import annotations

import asyncio
import json
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from services.pipeline.graph.store import GraphStore
from services.pipeline.ingest.loaders import SUPPORTED_SUFFIXES
from services.pipeline.workflow import run_pipeline
from services.pipeline.workflow.inbox import answer_question
from services.shared import config, llm

app = FastAPI(title="Slide Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# in-process registry of running builds so we don't double-launch
_running: dict[str, threading.Thread] = {}


def _store(project_id: str) -> GraphStore:
    db = config.project_db(project_id)
    if not db.exists():
        raise HTTPException(404, "project not found")
    return GraphStore(db)


# --------------------------------------------------------------------------- #
# Projects & uploads
# --------------------------------------------------------------------------- #


@app.post("/projects")
def create_project():
    pid = uuid.uuid4().hex[:12]
    pdir = config.project_dir(pid)
    (pdir / "files").mkdir(parents=True, exist_ok=True)
    (pdir / "artifacts").mkdir(parents=True, exist_ok=True)
    store = GraphStore(config.project_db(pid))
    store.set_run_state("created", "Project created", 0.0)
    store.close()
    return {"project_id": pid}


@app.post("/projects/{pid}/files")
async def upload_files(pid: str, files: list[UploadFile]):
    pdir = config.project_dir(pid)
    if not pdir.exists():
        raise HTTPException(404, "project not found")
    saved = []
    for f in files:
        suffix = Path(f.filename or "").suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise HTTPException(400, f"unsupported file type: {f.filename}")
        content = (await f.read()).decode("utf-8", errors="replace")
        (pdir / "files" / (f.filename or "untitled.txt")).write_text(content, encoding="utf-8")
        saved.append(f.filename)
    return {"saved": saved}


class BuildOpts(BaseModel):
    use_agent: bool = True


@app.post("/projects/{pid}/build")
def build(pid: str, opts: BuildOpts | None = None):
    pdir = config.project_dir(pid)
    files_dir = pdir / "files"
    if not files_dir.exists() or not any(files_dir.iterdir()):
        raise HTTPException(400, "no files uploaded")
    if pid in _running and _running[pid].is_alive():
        return {"status": "already_running"}

    use_agent = (opts.use_agent if opts else True) and llm.available()
    files = [(p.name, p.read_text(encoding="utf-8")) for p in sorted(files_dir.iterdir()) if p.is_file()]

    def worker():
        store = GraphStore(config.project_db(pid))
        try:
            run_pipeline(store, files, pdir / "artifacts", use_agent=use_agent)
        except Exception as exc:  # surface failures via run_state
            store.set_run_state("error", f"{type(exc).__name__}: {exc}", 1.0)
        finally:
            store.close()

    t = threading.Thread(target=worker, daemon=True)
    _running[pid] = t
    t.start()
    return {"status": "started", "use_agent": use_agent}


# --------------------------------------------------------------------------- #
# Progress (SSE)
# --------------------------------------------------------------------------- #


@app.get("/projects/{pid}/events")
async def events(pid: str):
    if not config.project_db(pid).exists():
        raise HTTPException(404, "project not found")

    async def stream():
        last = None
        while True:
            store = GraphStore(config.project_db(pid))
            state = store.get_run_state()
            store.close()
            if state and state != last:
                yield f"data: {json.dumps(state)}\n\n"
                last = state
                if state["stage"] in ("done", "error"):
                    break
            await asyncio.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream")


# --------------------------------------------------------------------------- #
# Question inbox
# --------------------------------------------------------------------------- #


@app.get("/projects/{pid}/questions")
def list_questions(pid: str):
    store = _store(pid)
    try:
        return {"questions": [q.model_dump() for q in store.list_questions()]}
    finally:
        store.close()


class AnswerBody(BaseModel):
    answer: str


@app.post("/projects/{pid}/questions/{qid}/answer")
def answer(pid: str, qid: str, body: AnswerBody):
    store = _store(pid)
    try:
        q = answer_question(store, qid, body.answer)
        if q is None:
            raise HTTPException(404, "question not found")
        return {"question": q.model_dump(), "rebuild_recommended": True}
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# Deck & graph
# --------------------------------------------------------------------------- #


@app.get("/projects/{pid}/deck", response_class=HTMLResponse)
def deck_html(pid: str):
    path = config.project_dir(pid) / "artifacts" / "deck.html"
    if not path.exists():
        raise HTTPException(404, "deck not built yet")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/projects/{pid}/deck.json")
def deck_json(pid: str):
    store = _store(pid)
    try:
        deck = store.get_deck()
        if deck is None:
            raise HTTPException(404, "deck not built yet")
        return deck.model_dump()
    finally:
        store.close()


@app.get("/projects/{pid}/graph")
def graph(pid: str):
    store = _store(pid)
    try:
        return JSONResponse(store.to_json())
    finally:
        store.close()


@app.get("/projects/{pid}/status")
def status(pid: str):
    store = _store(pid)
    try:
        return store.get_run_state() or {"stage": "created", "message": "", "progress": 0.0}
    finally:
        store.close()


@app.get("/healthz")
def healthz():
    return {"ok": True, "llm_enabled": llm.available()}
