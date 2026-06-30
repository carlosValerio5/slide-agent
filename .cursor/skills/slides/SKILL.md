---
name: slides
description: "Use when the user invokes /slides or asks to turn .md, .txt, or code files into slide presentations via a deterministic knowledge graph + judge agent workflow."
version: 1.2.0
disable-model-invocation: false
---

# /slides — Slide Agent

Turn any `.md`, `.txt`, or code file into a trustworthy reveal.js slide presentation.

The pipeline builds a deterministic knowledge graph (tree-sitter for code files, LLM-assisted for prose), runs a narrative agent that synthesizes audience-appropriate content from the graph, then verifies every claim via a designer → judge loop before rendering.

With no file arguments, the tool auto-discovers supported files in the current directory.

## Steps

### Step 1 — Check the `slide` CLI is installed

```bash
which slide
```

If the command is not found, tell the user to run `bash setup.sh` inside the slide-agent directory and stop.

### Step 2 — Ask audience and focus questions

Before running, ask the user these two questions conversationally:

1. **Who will view this presentation?**
   Options: `stakeholders`, `engineers`, `general`, `investors`

2. **What's the focus of this presentation?**
   Options: `technical`, `business`

If the user doesn't answer or says "default", use `general` and `technical`.
Map the answers to `--audience` and `--focus` flags for the CLI.

### Step 3 — Ask design style questions

Ask the user these three questions conversationally:

1. **Slide density** — How many bullet points per slide?
   Options: `light` (3 bullets), `balanced` (5 bullets), `dense` (6 bullets)
   Default: `balanced`

2. **Deck length** — How many slides in total?
   Options: `brief` (up to 12 slides), `standard` (up to 20 slides), `comprehensive` (up to 30 slides)
   Default: `standard`

3. **Bullet detail** — How long should each bullet point be?
   Options: `headline` (≤8 words), `summary` (≤12 words), `detailed` (≤16 words)
   Default: `summary`

If the user skips a question or says "default", omit that flag. Pass answers as `--density`, `--length`, and `--detail` flags to the CLI.

### Step 4 — Resolve input files

If the user provided file paths, validate that each exists. If a file is missing, report the exact path and stop.

If no file paths were provided, the CLI will auto-discover files in the current directory — no action needed.

### Step 5 — Run the pipeline

```bash
slide <files...> --audience <answer1> --focus <answer2> --density <answer3> --length <answer4> --detail <answer5> --out slide-out/ 2>&1
```

Omit any flag the user didn't answer (defaults apply).
Print progress lines to the user as they appear (`[XX%] ...` and `[discover] ...`).

### Step 6 — Parse the result

After the command finishes, find the line starting with `SLIDE_RESULT:` and parse the JSON after the colon.

- If `ok` is false: show the error and stop.
- If `ok` is true: proceed.

### Step 7 — Open the deck

```bash
uname -s
```

Open `deck_path` from the result:
- macOS (`Darwin`): `open "<deck_path>"`
- Linux: `xdg-open "<deck_path>" 2>/dev/null || echo "Deck ready at: <deck_path>"`
- Windows: `start "" "<deck_path>"`

### Step 8 — Surface open questions

If `open_questions` is non-empty, list them:

> The designer asked some questions and used defaults. Provide answers to improve the deck:
> 1. <text> (default: <default>)

Offer to rebuild if the user responds with answers.
