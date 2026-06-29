"""Renderer interface. reveal.js is the first implementation; a PPTX adapter
(python-pptx) will implement this same interface later with no pipeline changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from services.shared.design_philosophy import DesignPhilosophy
from services.shared.schemas import Deck


class Renderer(ABC):
    @abstractmethod
    def render(self, deck: Deck, philosophy: DesignPhilosophy) -> str:
        """Return the rendered artifact (HTML string for reveal.js)."""
        raise NotImplementedError
