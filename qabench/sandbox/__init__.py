"""Execution sandboxes for running untrusted, model-generated code."""

from __future__ import annotations

from qabench.config import Settings
from qabench.sandbox.docker_exec import DockerSandbox, docker_available
from qabench.sandbox.local_exec import LocalSandbox
from qabench.types import Sandbox

# Docker image tags built from docker/*.Dockerfile (see docker/README).
PYTHON_IMAGE = "qabench-python:latest"
NODE_IMAGE = "qabench-node:latest"
PLAYWRIGHT_IMAGE = "qabench-playwright:latest"


def get_sandbox(settings: Settings) -> Sandbox:
    """Pick a sandbox from settings (``auto`` prefers Docker when available)."""
    choice = settings.sandbox
    if choice == "docker":
        return DockerSandbox()
    if choice == "local":
        return LocalSandbox()
    return DockerSandbox() if docker_available() else LocalSandbox()


__all__ = [
    "NODE_IMAGE",
    "PLAYWRIGHT_IMAGE",
    "PYTHON_IMAGE",
    "DockerSandbox",
    "LocalSandbox",
    "docker_available",
    "get_sandbox",
]
