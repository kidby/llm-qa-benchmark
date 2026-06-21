"""The QA benchmark dashboard — soft, technical, minimal Reflex + Plotly app."""

from __future__ import annotations

import reflex as rx

from qabench_dash.data import SCORECARD_METRICS
from qabench_dash.state import State
from qabench_dash.theme import (
    BORDER,
    FONT_MONO,
    FONT_SANS,
    MUTED,
    PAGE,
    SURFACE,
    TEXT,
    TIER_COLORS,
)


def _panel(*children: rx.Component, **props: object) -> rx.Component:
    return rx.box(
        *children,
        background=SURFACE,
        border=f"1px solid {BORDER}",
        border_radius="10px",
        padding="1rem",
        width="100%",
        box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        transition="transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
        _hover={
            "transform": "translateY(-2px)",
            "box_shadow": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
        },
        **props,
    )


def _chart(fig: rx.Var, *, height: str = "360px") -> rx.Component:
    return _panel(rx.plotly(data=fig, width="100%", height=height))


def _tier_badge(tier: rx.Var) -> rx.Component:
    return rx.badge(
        tier,
        color_scheme="gray",
        variant="soft",
        style={
            "fontFamily": FONT_MONO,
            "color": rx.match(
                tier,
                ("A", TIER_COLORS["A"]),
                ("B", TIER_COLORS["B"]),
                ("C", TIER_COLORS["C"]),
                TIER_COLORS["n/a"],
            ),
        },
    )


def _scorecard_table() -> rx.Component:
    headers = [rx.table.column_header_cell("Model"), rx.table.column_header_cell("Tier")]
    headers += [
        rx.table.column_header_cell(m.replace("_", " "), style={"whiteSpace": "nowrap"})
        for m in SCORECARD_METRICS
    ]

    def row(r: rx.Var) -> rx.Component:
        cells = [
            rx.table.row_header_cell(r["model"], style={"fontFamily": FONT_MONO}),
            rx.table.cell(_tier_badge(r["tier"])),
        ]
        cells += [
            rx.table.cell(r[m], style={"fontFamily": FONT_MONO, "color": MUTED})
            for m in SCORECARD_METRICS
        ]
        return rx.table.row(*cells)

    return _panel(
        rx.heading("Per-model scorecard", size="4", color=TEXT, margin_bottom="0.5rem"),
        rx.text(
            "FP = tests failing on correct code · FN = mutants missed · "
            "lower hallucination is better.",
            size="1",
            color=MUTED,
            margin_bottom="0.75rem",
        ),
        rx.table.root(
            rx.table.header(rx.table.row(*headers)),
            rx.table.body(rx.foreach(State.scorecard, row)),
            variant="surface",
            size="1",
        ),
        style={"overflowX": "auto"},
    )


def _header() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.heading("QA Benchmark", size="6", color=TEXT, as_="h1", id="main-heading"),
                rx.text(
                    "Execution-based LLM evaluation for QA & test automation", 
                    size="2", 
                    color=MUTED, 
                    as_="p"
                ),
                spacing="0",
                align="start",
            ),
            rx.spacer(),
            rx.text("latest result per model", size="1", color=MUTED, as_="span"),
            rx.color_mode.button(id="color-mode-toggle", aria_label="Toggle color mode"),
            width="100%",
            align="center",
            spacing="3",
            padding_bottom="0.5rem",
        ),
        as_="header",
        id="app-header",
        position="sticky",
        top="0",
        z_index="100",
        backdrop_filter="blur(12px)",
        padding_top="1rem",
        background="transparent"
    )


def _metric_explorer() -> rx.Component:
    return _panel(
        rx.hstack(
            rx.heading(
                "Metric explorer", 
                size="4", 
                color=TEXT, 
                as_="h2", 
                id="metric-explorer-heading"
            ),
            rx.spacer(),
            rx.select(
                State.metrics, 
                value=State.metric, 
                on_change=State.set_metric, 
                id="metric-select", 
                aria_label="Select metric to explore"
            ),
            width="100%",
            align="center",
        ),
        rx.plotly(data=State.metric_chart, width="100%", height="340px"),
    )


def index() -> rx.Component:
    return rx.box(
        rx.vstack(
            _header(),
            rx.box(
                    rx.cond(
                        State.has_data,
                        rx.vstack(
                            _chart(State.leaderboard, height="440px"),
                            _scorecard_table(),
                            rx.grid(
                                _chart(State.cost_quality),
                                _chart(State.oneshot),
                                columns="2",
                                spacing="4",
                                width="100%",
                            ),
                            rx.grid(
                                _chart(State.category_bars),
                                _chart(State.pattern_matrix, height="440px"),
                                columns="2",
                                spacing="4",
                                width="100%",
                            ),
                            _chart(State.per_track, height="460px"),
                            rx.grid(
                                _chart(State.heatmap),
                                _metric_explorer(),
                                columns="2",
                                spacing="4",
                                width="100%",
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        rx.callout(
                            "No scored runs found. "
                            "Run `qabench run` then `qabench score <run_id>`.",
                            icon="info",
                            color_scheme="gray",
                        ),
                    ),
                    as_="main",
                    id="main-content"
                ),
                spacing="4",
                width="100%",
                max_width="1200px",
                margin="0 auto",
                padding="1.5rem",
            ),
        background=PAGE,
        min_height="100vh",
        font_family=FONT_SANS,
    )


app = rx.App(
    # appearance="inherit" follows the system light/dark preference; the
    # rx.color_mode.button() in the header lets users override it.
    theme=rx.theme(appearance="inherit", accent_color="gray", gray_color="slate", radius="medium"),
    style={"fontFamily": FONT_SANS},
)
app.add_page(
    index, 
    title="QA Benchmark Dashboard",
    description="An execution-based LLM evaluation benchmark for QA and test automation tasks.",
    meta=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "theme-color", "content": "#111113"},
    ]
)
