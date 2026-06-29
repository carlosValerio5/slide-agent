"""The design philosophy: a versioned, declarative ruleset.

This is the shared contract between the designer agent (which must follow it)
and the judge agent (which enforces it). Keeping it declarative means a rule
can be both fed into a prompt and mechanically checked.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Theme(BaseModel):
    name: str = "Aurora"
    bg: str = "#0f172a"
    surface: str = "#1e293b"
    text: str = "#e2e8f0"
    accent: str = "#38bdf8"
    muted: str = "#94a3b8"
    font_heading: str = "'Inter', system-ui, sans-serif"
    font_body: str = "'Inter', system-ui, sans-serif"


class DesignPhilosophy(BaseModel):
    version: str = "1.0.0"
    theme: Theme = Field(default_factory=Theme)

    # mechanically-checkable rules (the judge enforces these)
    max_bullets_per_slide: int = 6
    max_words_per_bullet: int = 16
    max_title_words: int = 10
    min_slides: int = 4
    max_slides: int = 30
    require_title_slide: bool = True
    require_citation_for_metrics: bool = True

    # qualitative guidance (the designer follows these; surfaced in prompts)
    tone: str = "clear, confident, plain language for a non-technical audience"
    principles: list[str] = Field(
        default_factory=lambda: [
            "One idea per slide; lead with the takeaway.",
            "Prefer concrete numbers over adjectives, and always cite them.",
            "Use short parallel bullets, not paragraphs.",
            "Keep titles to a single line.",
            "Maintain strong contrast and generous whitespace.",
        ]
    )

    def as_prompt(self) -> str:
        lines = [
            f"DESIGN PHILOSOPHY v{self.version} (tone: {self.tone}).",
            "Hard limits:",
            f"  - <= {self.max_bullets_per_slide} bullets per slide",
            f"  - <= {self.max_words_per_bullet} words per bullet",
            f"  - <= {self.max_title_words} words per title",
            f"  - {self.min_slides}-{self.max_slides} slides total",
            "  - include a title slide" if self.require_title_slide else "",
            "  - every metric/number must carry a citation"
            if self.require_citation_for_metrics
            else "",
            "Principles:",
        ]
        lines += [f"  - {p}" for p in self.principles]
        return "\n".join(l for l in lines if l)


DEFAULT_PHILOSOPHY = DesignPhilosophy()
