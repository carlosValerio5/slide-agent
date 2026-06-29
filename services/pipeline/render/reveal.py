"""reveal.js HTML renderer.

Turns the renderer-agnostic Deck into a self-contained reveal.js presentation
(CDN assets), themed from the design philosophy. Citations are rendered as
small superscript markers with a per-slide source footer.
"""
from __future__ import annotations

import html

from services.shared.design_philosophy import DesignPhilosophy
from services.shared.schemas import Deck, Slide

from .base import Renderer

_CDN = "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0"


class RevealRenderer(Renderer):
    def render(self, deck: Deck, philosophy: DesignPhilosophy) -> str:
        t = philosophy.theme
        slides_html = "\n".join(self._slide(s) for s in deck.slides)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(deck.title)}</title>
<link rel="stylesheet" href="{_CDN}/dist/reveal.css">
<link rel="stylesheet" href="{_CDN}/dist/theme/black.css">
<style>
:root {{ --accent: {t.accent}; }}
.reveal {{ font-family: {t.font_body}; color: {t.text}; }}
.reveal h1, .reveal h2, .reveal h3 {{ font-family: {t.font_heading}; color: #fff; text-transform: none; letter-spacing: -0.01em; }}
.reveal .slides section {{ text-align: left; }}
.reveal .backgrounds {{ background: {t.bg}; }}
.reveal section {{ background: {t.bg}; }}
.reveal .title-slide {{ text-align: center; }}
.reveal .accent {{ color: {t.accent}; }}
.reveal ul {{ display: block; }}
.reveal li {{ margin: 0.4em 0; }}
.reveal .cite {{ color: {t.accent}; font-size: 0.5em; vertical-align: super; margin-left: 0.15em; }}
.reveal .sources {{ position: absolute; bottom: 12px; left: 40px; right: 40px;
  font-size: 0.32em; color: {t.muted}; border-top: 1px solid {t.surface}; padding-top: 6px; }}
.reveal .statement {{ font-size: 1.4em; font-weight: 600; }}
.reveal blockquote {{ border-left: 4px solid {t.accent}; padding-left: 0.6em; color: {t.text}; }}
</style>
</head>
<body>
<div class="reveal"><div class="slides">
{slides_html}
</div></div>
<script src="{_CDN}/dist/reveal.js"></script>
<script>Reveal.initialize({{ hash: true, slideNumber: 'c/t', transition: 'fade' }});</script>
</body>
</html>"""

    # ---- per-slide rendering ---------------------------------------------- #

    def _slide(self, s: Slide) -> str:
        cite_index: dict[str, int] = {}
        body = self._body(s, cite_index)
        sources = self._sources(cite_index)
        title = html.escape(s.title)

        if s.layout == "title":
            return (
                f'<section class="title-slide"><h1>{title}</h1>{body}</section>'
            )
        if s.layout == "section":
            return f'<section><h2 class="accent">{title}</h2>{body}</section>'
        if s.layout == "statement":
            return f'<section><div class="statement">{body}</div>{sources}</section>'

        heading = f"<h2>{title}</h2>" if title else ""
        return f"<section>{heading}{body}{sources}</section>"

    def _body(self, s: Slide, cite_index: dict[str, int]) -> str:
        bullets = [e for e in s.elements if e.kind == "bullet"]
        others = [e for e in s.elements if e.kind != "bullet"]
        parts: list[str] = []
        for e in others:
            txt = html.escape(e.text) + self._cite_markers(e.citations, cite_index)
            if e.kind == "heading":
                parts.append(f"<h3>{txt}</h3>")
            elif e.kind == "quote":
                parts.append(f"<blockquote>{txt}</blockquote>")
            else:
                parts.append(f"<p>{txt}</p>")
        if bullets:
            items = "".join(
                f"<li>{html.escape(b.text)}{self._cite_markers(b.citations, cite_index)}</li>"
                for b in bullets
            )
            parts.append(f"<ul>{items}</ul>")
        return "\n".join(parts)

    def _cite_markers(self, citations, cite_index: dict[str, int]) -> str:
        out = []
        for c in citations:
            key = f"{c.kind}:{c.ref}"
            if key not in cite_index:
                cite_index[key] = len(cite_index) + 1
            out.append(f'<sup class="cite">[{cite_index[key]}]</sup>')
        return "".join(out)

    def _sources(self, cite_index: dict[str, int]) -> str:
        if not cite_index:
            return ""
        items = []
        for key, n in sorted(cite_index.items(), key=lambda kv: kv[1]):
            kind, ref = key.split(":", 1)
            label = "source" if kind == "graph" else "external"
            items.append(f"[{n}] {html.escape(ref)} ({label})")
        return '<div class="sources">' + " &nbsp; ".join(items) + "</div>"
