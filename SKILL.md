---
name: slides
description: "Use when the user invokes /slides to turn .md, .txt, or code files into slide presentations via a deterministic knowledge graph + judge agent workflow."
version: 1.1.0
argument-hint: "[file...] [--audience <a>] [--focus <f>] [--no-agent]"
allowed-tools: ["Bash", "Read"]
---

# /slides — Slide Agent

Turn any `.md`, `.txt`, or code file into a trustworthy reveal.js slide presentation.

The pipeline builds a deterministic knowledge graph (tree-sitter for code files, LLM-assisted for prose), runs a narrative agent that synthesizes audience-appropriate content from the graph, then verifies every claim via a designer → judge loop before rendering.

With no file arguments, the tool auto-discovers supported files in the current directory.

**Arguments:** `$ARGUMENTS`

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

### Step 3 — Resolve input files

If `$ARGUMENTS` contains file paths, validate that each exists. If a file is missing, report the exact path and stop.

If `$ARGUMENTS` is empty (no file paths), the CLI will auto-discover files in the current directory — no action needed.

### Step 4 — Run the pipeline

```bash
slide $ARGUMENTS --audience <answer1> --focus <answer2> --out slide-out/ 2>&1
```

If no audience/focus was provided, omit those flags (defaults apply).
Print progress lines to the user as they appear (`[XX%] ...` and `[discover] ...`).

### Step 5 — Parse the result

After the command finishes, find the line starting with `SLIDE_RESULT:` and parse the JSON after the colon.

- If `ok` is false: show the error and stop.
- If `ok` is true: proceed.

### Step 6 — Open the deck

```bash
uname -s
```

Open `deck_path` from the result:
- macOS (`Darwin`): `open "<deck_path>"`
- Linux: `xdg-open "<deck_path>" 2>/dev/null || echo "Deck ready at: <deck_path>"`
- Windows: `start "" "<deck_path>"`

### Step 7 — Surface open questions

If `open_questions` is non-empty, list them:

> The designer asked some questions and used defaults. Provide answers to improve the deck:
> 1. <text> (default: <default>)

Offer to rebuild if the user responds with answers.
