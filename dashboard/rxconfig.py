"""Reflex configuration for the QA benchmark dashboard."""

import reflex as rx

config = rx.Config(
    app_name="qabench_dash",
    frontend_port=3000,
    telemetry_enabled=False,
)
