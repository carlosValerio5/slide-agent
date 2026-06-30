"""The design philosophy: a versioned, declarative ruleset.

This is the shared contract between the designer agent (which must follow it)
and the judge agent (which enforces it). Keeping it declarative means a rule
can be both fed into a prompt and mechanically checked.
"""
from __future__ import annotations

from typing import Literal

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


_AUDIENCE_LABELS = {
    "stakeholders": "company stakeholders",
    "engineers": "software engineers",
    "general": "a general audience",
    "investors": "investors",
}

_GUIDANCE: dict[tuple[str, str], str] = {
    ("engineers", "technical"): (
        "Audience are software engineers. Emphasize architecture, key abstractions, "
        "data flow, and notable design decisions. Use precise component names from "
        "the graph. Moderate jargon is fine. Show how components connect."
    ),
    ("engineers", "business"): (
        "Audience are software engineers but focus is business outcomes. Frame "
        "technical choices in terms of their product impact and trade-offs."
    ),
    ("general", "technical"): (
        "General audience. Explain what the system does in plain language. "
        "Use analogies over implementation detail. Minimize jargon. "
        "Lead each slide with the takeaway, not the mechanism."
    ),
    ("general", "business"): (
        "General audience, business framing. Focus on what the system enables, "
        "outcomes it delivers, and problems it solves. No code-level detail."
    ),
    ("stakeholders", "technical"): (
        "Company stakeholders. Provide a capabilities overview with light "
        "architectural context. Connect technical components to business value."
    ),
    ("stakeholders", "business"): (
        "Company stakeholders. Frame entirely around value, capabilities, and "
        "outcomes. Avoid code-level detail. Lead every slide with the business outcome."
    ),
    ("investors", "technical"): (
        "Investors with technical interest. Highlight technical differentiation, "
        "scalability, and defensibility. Keep it crisp and business-relevant."
    ),
    ("investors", "business"): (
        "Investors. Frame around value, market opportunity, outcomes, and "
        "differentiation. Avoid code-level detail. Lead with the benefit per slide."
    ),
}


class AudienceProfile(BaseModel):
    audience: Literal["stakeholders", "engineers", "general", "investors"] = "general"
    focus: Literal["technical", "business"] = "technical"

    def label(self) -> str:
        """Human label for use in the title slide."""
        return _AUDIENCE_LABELS.get(self.audience, self.audience)

    def subtitle(self) -> str:
        return f"Prepared for {self.label()}"

    def as_prompt(self) -> str:
        """Concrete guidance injected into the narrator's system prompt."""
        return _GUIDANCE.get(
            (self.audience, self.focus),
            "Present clearly and concisely for a general audience.",
        )

    def tune(self, philo: DesignPhilosophy) -> DesignPhilosophy:
        """Return a copy of philo with tone/principles adjusted for this audience."""
        copy = philo.model_copy()
        if self.focus == "business":
            copy.tone = "outcome-focused, plain language, no code-level detail"
            copy.principles = [
                "Lead every slide with the business outcome or benefit.",
                "Prefer concrete capabilities over implementation mechanics.",
                "Use short parallel bullets, not paragraphs.",
                "Keep titles to a single line.",
                "Maintain strong contrast and generous whitespace.",
            ]
        elif self.audience == "engineers":
            copy.tone = "precise, technical, architecture-focused"
            copy.principles = [
                "One concept per slide; lead with the design decision or pattern.",
                "Name components exactly as they appear in the codebase.",
                "Use short parallel bullets, not paragraphs.",
                "Keep titles to a single line.",
                "Maintain strong contrast and generous whitespace.",
            ]
        return copy
