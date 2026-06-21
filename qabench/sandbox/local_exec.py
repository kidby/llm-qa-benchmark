"""Local subprocess sandbox — runs commands in a temp dir with a timeout.

Less isolated than Docker (no namespace/network limits), but needs no daemon and
is used for tests and as a fallback. ``python``/``node`` in a command are resolved
to the current interpreter / a discovered node binary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from qabench.sandbox.workdir import decode, write_files
from qabench.types import ExecResult

_TIMEOUT_EXIT = 124


def _resolve(command: list[str]) -> list[str]:
    """Map the well-known interpreters to concrete binaries on this host."""
    if not command:
        return command
    head, *rest = command
    if head == "python":
        return [sys.executable, *rest]
    if head == "node":
        return [shutil.which("node") or "node", *rest]
    if head == "npx":
        return [shutil.which("npx") or "npx", *rest]
    return command


class LocalSandbox:
    """Runs files+command on the host inside a throwaway directory."""

    def run(
        self,
        *,
        image: str,
        files: dict[str, str],
        command: list[str],
        timeout_s: int = 120,
    ) -> ExecResult:
        """Write ``files``, run ``command`` in that dir, capture the result."""
        del image  # the local sandbox ignores the image tag
        with tempfile.TemporaryDirectory(prefix="qabench-") as tmp:
            workdir = Path(tmp)
            write_files(workdir, files)
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
            start = time.perf_counter()
            try:
                proc = subprocess.run(
                    _resolve(command),
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    env=env,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return ExecResult(
                    exit_code=_TIMEOUT_EXIT,
                    stdout=decode(exc.stdout),
                    stderr=decode(exc.stderr),
                    timed_out=True,
                    duration_s=time.perf_counter() - start,
                )
            return ExecResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_s=time.perf_counter() - start,
            )
