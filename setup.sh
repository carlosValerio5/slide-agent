#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${HOME}/.claude/skills/slides"
CLAUDE_MD="${HOME}/.claude/CLAUDE.md"

echo "Installing slide-agent Python package..."
pip install -e "$SCRIPT_DIR" -q

echo "Installing Claude Code skill to $SKILL_DIR ..."
mkdir -p "$SKILL_DIR/.claude-plugin"
cp "$SCRIPT_DIR/SKILL.md"                       "$SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/.claude-plugin/plugin.json"     "$SKILL_DIR/.claude-plugin/plugin.json"

echo "Registering skill in $CLAUDE_MD ..."
CLAUDE_MD_ENTRY='# slides
- **slides** (`~/.claude/skills/slides/SKILL.md`) - turn .md, .txt, or code files into slide presentations via a deterministic knowledge graph + judge agent. Trigger: `/slides`
When the user types `/slides`, invoke the Skill tool with `skill: "slides"` before doing anything else.'

# Append only if not already present (idempotent)
if ! grep -qF '# slides' "$CLAUDE_MD" 2>/dev/null; then
    printf '\n%s\n' "$CLAUDE_MD_ENTRY" >> "$CLAUDE_MD"
    echo "  Added /slides entry to CLAUDE.md."
else
    echo "  /slides entry already present in CLAUDE.md — skipping."
fi

echo ""
echo "Done! Restart Claude Code, then type: /slides <your-file.md>"
