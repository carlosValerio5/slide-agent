---
name: slides
description: "Use when the user invokes /slides to turn .md, .txt, or code files into slide presentations via a deterministic knowledge graph + judge agent workflow."
version: 1.0.0
argument-hint: "<file> [file2...] [--no-agent]"
allowed-tools: ["Bash", "Read"]
---

# /slides — Slide Agent

Turn any `.md`, `.txt`, or code file into a trustworthy reveal.js slide presentation.

The pipeline builds a deterministic knowledge graph (tree-sitter for code files, LLM-assisted for prose), then runs a designer → judge loop that verifies every claim before rendering.

**Arguments:** `$ARGUMENTS`

## Steps

### Step 1 — Check the `slide` CLI is installed

```bash
which slide
```

If the command is not found, tell the user to run `bash setup.sh` inside the slide-agent directory and stop.

### Step 2 — Validate input files

Read each file path from `$ARGUMENTS` (stop before any `--` flags). Confirm each file exists. If a file is missing, report the exact path and stop.

### Step 3 — Run the pipeline

```bash
slide $ARGUMENTS --out slide-out/ 2>&1
```

Print progress lines to the user as they appear (`[XX%] ...`).

### Step 4 — Parse the result

After the command finishes, find the line starting with `SLIDE_RESULT:` and parse the JSON after the colon.

- If `ok` is false: show the error and stop.
- If `ok` is true: proceed.

### Step 5 — Open the deck

```bash
uname -s
```

Open `deck_path` from the result:
- macOS (`Darwin`): `open "<deck_path>"`
- Linux: `xdg-open "<deck_path>" 2>/dev/null || echo "Deck ready at: <deck_path>"`
- Windows: `start "" "<deck_path>"`

### Step 6 — Surface open questions

If `open_questions` is non-empty, list them:

> The designer asked some questions and used defaults. Provide answers to improve the deck:
> 1. <text> (default: <default>)

Offer to rebuild if the user responds with answers.
