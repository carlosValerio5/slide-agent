"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type RunState = { stage: string; message: string; progress: number };
type Question = {
  id: string;
  text: string;
  options: string[];
  default: string;
  status: "open" | "answered";
  answer: string | null;
};

const STAGES = [
  ["ingesting", "Reading files"],
  ["graph_building", "Building knowledge graph"],
  ["researching", "Researching context"],
  ["designing", "Designing slides"],
  ["judging", "Verifying facts & design"],
  ["rendering", "Rendering deck"],
  ["done", "Ready"],
];

export default function Home() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [hot, setHot] = useState(false);
  const [run, setRun] = useState<RunState | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [deckReady, setDeckReady] = useState(false);
  const [building, setBuilding] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // create a project on first load
  useEffect(() => {
    fetch("/api/projects", { method: "POST" })
      .then((r) => r.json())
      .then((d) => setProjectId(d.project_id))
      .catch(() => {});
  }, []);

  const refreshQuestions = useCallback(() => {
    if (!projectId) return;
    fetch(`/api/projects/${projectId}/questions`)
      .then((r) => r.json())
      .then((d) => setQuestions(d.questions || []))
      .catch(() => {});
  }, [projectId]);

  const onFiles = (list: FileList | null) => {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list)]);
  };

  const upload = async () => {
    if (!projectId || files.length === 0) return;
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    await fetch(`/api/projects/${projectId}/files`, { method: "POST", body: fd });
  };

  const build = async () => {
    if (!projectId) return;
    setBuilding(true);
    setDeckReady(false);
    await upload();
    await fetch(`/api/projects/${projectId}/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_agent: true }),
    });

    // stream progress via SSE
    const es = new EventSource(`/api/projects/${projectId}/events`);
    es.onmessage = (ev) => {
      const state: RunState = JSON.parse(ev.data);
      setRun(state);
      refreshQuestions();
      if (state.stage === "done") {
        setDeckReady(true);
        setBuilding(false);
        es.close();
      } else if (state.stage === "error") {
        setBuilding(false);
        es.close();
      }
    };
    es.onerror = () => es.close();
  };

  const answer = async (q: Question, value: string) => {
    if (!projectId) return;
    await fetch(`/api/projects/${projectId}/questions/${q.id}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer: value }),
    });
    refreshQuestions();
  };

  const stageIndex = STAGES.findIndex(([s]) => s === run?.stage);
  const openCount = questions.filter((q) => q.status === "open").length;

  return (
    <div className="wrap">
      <h1>Slide Agent</h1>
      <p className="sub">
        Upload your notes. We build a knowledge graph from them, then research,
        design, and fact-check a presentation you can trust.
      </p>

      {/* Upload */}
      <div className="card">
        <h2>1 · Upload your files</h2>
        <div
          className={`drop${hot ? " hot" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setHot(true);
          }}
          onDragLeave={() => setHot(false)}
          onDrop={(e) => {
            e.preventDefault();
            setHot(false);
            onFiles(e.dataTransfer.files);
          }}
          onClick={() => inputRef.current?.click()}
        >
          Drag &amp; drop .txt or .md files here, or click to choose
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".txt,.md,.markdown,.text"
            style={{ display: "none" }}
            onChange={(e) => onFiles(e.target.files)}
          />
        </div>
        {files.length > 0 && (
          <ul className="files">
            {files.map((f, i) => (
              <li key={i}>📄 {f.name} <span className="pill">{Math.ceil(f.size / 1024)} KB</span></li>
            ))}
          </ul>
        )}
        <div className="row" style={{ marginTop: 16 }}>
          <button onClick={build} disabled={!projectId || files.length === 0 || building}>
            {building ? "Working…" : "Build presentation"}
          </button>
          <span className="muted">{projectId ? `project ${projectId}` : "connecting…"}</span>
        </div>
      </div>

      {/* Progress */}
      {run && (
        <div className="card">
          <h2>2 · Progress</h2>
          <div className="timeline">
            {STAGES.map(([s, label], i) => {
              const cls =
                run.stage === s ? "active" : i < stageIndex ? "complete" : "";
              return (
                <div key={s} className={`stage ${cls}`}>
                  <span className="dot" />
                  {label}
                </div>
              );
            })}
          </div>
          <div className="bar">
            <div style={{ width: `${Math.round((run.progress || 0) * 100)}%` }} />
          </div>
          <span className="muted">{run.message}</span>
        </div>
      )}

      {/* Question inbox */}
      {questions.length > 0 && (
        <div className="card">
          <h2>
            Designer questions
            {openCount > 0 && <span className="badge">{openCount}</span>}
          </h2>
          <p className="muted" style={{ marginTop: -4 }}>
            These never block the build — we proceed with a sensible default and
            revise affected slides when you answer.
          </p>
          {questions.map((q) => (
            <div key={q.id} className={`q${q.status === "answered" ? " answered" : ""}`}>
              <div>{q.text}</div>
              {q.status === "answered" ? (
                <div className="muted">✓ {q.answer}</div>
              ) : (
                <div className="opts">
                  {(q.options.length ? q.options : [q.default]).map((opt) => (
                    <button key={opt} className="ghost" onClick={() => answer(q, opt)}>
                      {opt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Deck preview */}
      {deckReady && projectId && (
        <div className="card">
          <h2>3 · Your presentation</h2>
          <iframe className="deck" src={`/api/projects/${projectId}/deck`} title="deck" />
          <div className="row" style={{ marginTop: 12 }}>
            <a className="dl" href={`/api/projects/${projectId}/deck`} target="_blank" rel="noreferrer">
              Open full screen ↗
            </a>
            <span className="muted">Tip: press “E” then print to PDF from the deck.</span>
          </div>
        </div>
      )}
    </div>
  );
}
