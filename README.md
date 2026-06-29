# Slide Agent

Turn plain text files into **trustworthy** slide presentations.

The hard problem isn't generating slides — it's making sure the deck only says
what your source material supports. Slide Agent solves this by compiling your
uploaded files into a **deterministic knowledge graph** (the single source of
truth) and then running an agent workflow on top of it where a **judge agent**
verifies every claim against the graph and enforces the design philosophy before
anything ships.

## How it works

```
Upload → Ingest → Deterministic Knowledge Graph (agent-assisted) →
Query Tool → Researcher → Designer ⇄ Judge (loop) → reveal.js deck
```

1. **Ingest** — `.txt`/`.md` files are split into provenance-tracked blocks (no LLM).
2. **Knowledge graph** — a rule-based pass builds a graph under a *closed
   ontology*; an extraction agent only *proposes* extra structure, and a
   deterministic validator drops anything off-ontology or not literally present
   in the source. Same files → same graph.
3. **Query tool** — agents learn facts only through a typed query API, so
   everything they use is graph-backed and traceable.
4. **Researcher** — gathers *external* cited context, stored separately from the
   source-of-truth graph (never merged in).
5. **Designer** — scaffolds a renderer-agnostic deck following the design
   philosophy. Can ask you questions **asynchronously** (non-blocking inbox).
6. **Judge** — verifies (a) every figure/claim is backed by graph provenance or a
   cited note, and (b) the deck obeys the design philosophy. Loops back to the
   designer on failure.
7. **Render** — reveal.js HTML now; a PPTX adapter implements the same renderer
   interface later.

## Install as a Claude Code skill

### Global install (skill available in every Claude Code session)

```bash
git clone https://github.com/carlosValerio5/slide-agent.git
cd slide-agent
bash setup.sh
```

`setup.sh` does three things:
1. `pip install -e .` — installs the `slide` CLI and its dependencies
2. Copies `SKILL.md` and `plugin.json` to `~/.claude/skills/slides/`
3. Appends a trigger entry to `~/.claude/CLAUDE.md` so Claude Code invokes the skill automatically when you type `/slides`

Restart Claude Code, then use it from any project:

```
/slides my-notes.md
/slides src/main.py --no-agent
```

### Project-only install (skill scoped to one repo)

If you only want `/slides` available inside a specific project, skip `setup.sh` and configure it manually:

**1. Install the Python package** (once, into your environment):

```bash
cd /path/to/slide-agent
pip install -e .
```

**2. Copy the skill files** into your project's `.claude/skills/` directory:

```bash
mkdir -p /your/project/.claude/skills/slides/.claude-plugin
cp /path/to/slide-agent/SKILL.md      /your/project/.claude/skills/slides/
cp /path/to/slide-agent/.claude-plugin/plugin.json \
                                       /your/project/.claude/skills/slides/.claude-plugin/
```

**3. Add the trigger** to your project's `CLAUDE.md` (create it if it doesn't exist):

```markdown
# slides
- **slides** (`.claude/skills/slides/SKILL.md`) - build slide decks from files. Trigger: `/slides`
When the user types `/slides`, invoke the Skill tool with `skill: "slides"` before doing anything else.
```

Now `/slides` works only when Claude Code is open inside that project.

---

## Run it locally

### Backend (FastAPI)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# optional: enables the agentic steps (extraction, research, designer refinement)
export ANTHROPIC_API_KEY=sk-ant-...

uvicorn services.api.main:app --reload --port 8000
```

Without an API key everything still runs **deterministically offline** — the
agent steps degrade gracefully and the pipeline produces a graph + deck.

### Frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev          # http://localhost:3000  (proxies /api → :8000)
```

Open http://localhost:3000, drop in a `.md`/`.txt` file, and click **Build
presentation**.

## Tests

```bash
pytest -q
```

Covers graph determinism, provenance, validator rejection of fabricated
proposals, judge veracity/design enforcement, and the non-blocking question
inbox.

## Layout

```
services/
  shared/      schemas, closed ontology, design philosophy, Anthropic wrapper
  pipeline/
    ingest/    loaders + deterministic block segmentation
    graph/     deterministic builder, agent-assisted extraction, validator, SQLite store
    query/     typed query API + Anthropic tool definitions
    workflow/  researcher, designer, judge, orchestrator, async inbox
    render/    renderer interface + reveal.js implementation
  api/         FastAPI app (upload, build, SSE progress, inbox, deck, graph)
apps/web/      Next.js UI (upload, progress timeline, question inbox, deck preview)
tests/         pytest suite + sample fixture
```
