"""Geometry-based form reconstruction contracts."""

from __future__ import annotations

from engineering_di.models import FormField, Page


class FormReconstructor:
    """Detect form fields after layout and cell reconstruction."""

    def reconstruct(self, page: Page) -> list[FormField]:
        return []
