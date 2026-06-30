#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SKILL_DIR="${HOME}/.claude/skills/slides"
CURSOR_SKILL_DIR="${HOME}/.cursor/skills/slides"
CLAUDE_MD="${HOME}/.claude/CLAUDE.md"

# Target platform: claude | cursor | both (default: both)
TARGET="${1:-both}"

echo "Installing slide-agent Python package..."
pip install -e "$SCRIPT_DIR" -q

install_claude() {
    echo "Installing Claude Code skill to $CLAUDE_SKILL_DIR ..."
    mkdir -p "$CLAUDE_SKILL_DIR/.claude-plugin"
    cp "$SCRIPT_DIR/SKILL.md"                   "$CLAUDE_SKILL_DIR/SKILL.md"
    cp "$SCRIPT_DIR/.claude-plugin/plugin.json" "$CLAUDE_SKILL_DIR/.claude-plugin/plugin.json"

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
}

install_cursor() {
    echo "Installing Cursor skill to $CURSOR_SKILL_DIR ..."
    mkdir -p "$CURSOR_SKILL_DIR"
    cp "$SCRIPT_DIR/.cursor/skills/slides/SKILL.md" "$CURSOR_SKILL_DIR/SKILL.md"
    echo "  Cursor auto-discovers the skill from its description — no trigger file needed."
}

case "$TARGET" in
    claude) install_claude ;;
    cursor) install_cursor ;;
    both)   install_claude; install_cursor ;;
    *)
        echo "Unknown target '$TARGET'. Use: claude | cursor | both" >&2
        exit 1
        ;;
esac

echo ""
echo "Done! Restart your agent, then type: /slides <your-file.md>"
