"""Design tokens for the dashboard — soft, muted, technical; light/dark aware.

All styling flows through the tokens defined here; components and charts never
hardcode colors inline. UI chrome uses Radix gray tokens via ``rx.color(...)``
(these compile to CSS variables like ``var(--gray-12)``, so they adapt to the
active light/dark color mode). Plotly bakes colors into the figure, so charts use
a transparent background plus a neutral mid-gray ink that reads on both themes,
with a muted, low-contrast categorical palette.
"""

from __future__ import annotations

import reflex as rx

# --- UI chrome (adaptive via the Radix gray scale → CSS variables) ----------
TEXT = rx.color("gray", 12)
MUTED = rx.color("gray", 11)
PAGE = rx.color("gray", 1)
SURFACE = rx.color("gray", 2)
BORDER = rx.color("gray", 6)

# --- Typography -------------------------------------------------------------
FONT_SANS = "Inter, system-ui, -apple-system, sans-serif"
FONT_MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace"

# --- Chart colors (theme-agnostic: transparent bg + neutral ink) ------------
CHART_INK = "#8b9098"
CHART_GRID = "rgba(140, 140, 150, 0.16)"
CHART_BG = "rgba(0, 0, 0, 0)"

# Muted, low-contrast tier + categorical colors.
TIER_COLORS = {"A": "#5f8c74", "B": "#b09a64", "C": "#b57f72", "n/a": "#9aa0a6"}
PALETTE = ["#7c8aa5", "#6f9b86", "#bca56e", "#b58a8a", "#8f86a8", "#7fa3a3"]


def plotly_layout(title: str) -> dict[str, object]:
    """A consistent, restrained Plotly layout shared by every chart."""
    axis = {"gridcolor": CHART_GRID, "zerolinecolor": CHART_GRID}
    return {
        "title": {"text": title, "font": {"size": 15, "color": CHART_INK, "family": FONT_SANS}},
        "template": "plotly_white",
        "font": {"family": FONT_SANS, "color": CHART_INK, "size": 12},
        "paper_bgcolor": CHART_BG,
        "plot_bgcolor": CHART_BG,
        "margin": {"l": 56, "r": 24, "t": 48, "b": 48},
        "colorway": PALETTE,
        "xaxis": axis,
        "yaxis": dict(axis),
    }
