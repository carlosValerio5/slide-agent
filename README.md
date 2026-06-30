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

## Install as a skill (Cursor or Claude Code)

Slide Agent runs as an **agent skill** on either platform. The agentic steps go
through whichever CLI is on your PATH — **`cursor-agent`** for Cursor or
**`claude`** for Claude Code — so no API key is needed in this process; each CLI
carries its own auth. The deterministic graph + deck still build offline when
neither CLI is present.

The same `slide` CLI and the same deterministic pipeline power both platforms.
Only the agent backend differs, selected with `SLIDE_AGENT_LLM`:

| Env var | Values | Default | Purpose |
| --- | --- | --- | --- |
| `SLIDE_AGENT_LLM` | `claude`, `cursor`, `auto` | `auto` | Pick the agent backend. `auto` prefers `claude`, then `cursor-agent`. |
| `SLIDE_AGENT_CLAUDE_MODEL` | model id | unset | Override the Claude Code model (else the CLI default). |
| `SLIDE_AGENT_CURSOR_MODEL` | model id (e.g. `gpt-5`, `sonnet-4`) | unset | Override the Cursor model (else the CLI default). |

### Global install (skill available in every session)

```bash
git clone https://github.com/carlosValerio5/slide-agent.git
cd slide-agent
bash setup.sh            # installs for both Cursor and Claude Code
# or target one platform:
bash setup.sh cursor
bash setup.sh claude
```

`setup.sh` always runs `pip install -e .` (the `slide` CLI + deps), then:
- **Cursor** — copies `.cursor/skills/slides/SKILL.md` to `~/.cursor/skills/slides/`.
  Cursor auto-discovers the skill from its `description`; invoke it with `/slides`.
- **Claude Code** — copies `SKILL.md` + `plugin.json` to `~/.claude/skills/slides/`
  and appends a `/slides` trigger to `~/.claude/CLAUDE.md`.

Restart your agent, then use it from any project:

```
/slides my-notes.md
/slides src/main.py --no-agent
```

### Project-only install (skill scoped to one repo)

If you only want `/slides` available inside a specific project, skip `setup.sh`
and configure it manually. Install the Python package once into your
environment:

```bash
cd /path/to/slide-agent
pip install -e .
```

**Cursor** — copy the skill into the project's `.cursor/skills/` directory:

```bash
mkdir -p /your/project/.cursor/skills/slides
cp /path/to/slide-agent/.cursor/skills/slides/SKILL.md \
                                       /your/project/.cursor/skills/slides/SKILL.md
```

Cursor picks up the skill on startup and surfaces it via `/slides`.

**Claude Code** — copy the skill files into the project's `.claude/skills/`
directory and register the trigger:

```bash
mkdir -p /your/project/.claude/skills/slides/.claude-plugin
cp /path/to/slide-agent/SKILL.md      /your/project/.claude/skills/slides/
cp /path/to/slide-agent/.claude-plugin/plugin.json \
                                       /your/project/.claude/skills/slides/.claude-plugin/
```

Add the trigger to your project's `CLAUDE.md` (create it if it doesn't exist):

```markdown
# slides
- **slides** (`.claude/skills/slides/SKILL.md`) - build slide decks from files. Trigger: `/slides`
When the user types `/slides`, invoke the Skill tool with `skill: "slides"` before doing anything else.
```

Now `/slides` works only when the agent is open inside that project.

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
  shared/      schemas, closed ontology, design philosophy, agent CLI wrapper (claude / cursor-agent)
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
