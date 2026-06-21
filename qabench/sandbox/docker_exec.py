"""Docker sandbox — runs untrusted generated code in a disposable container.

Locked down with ``--network none``, memory/CPU/PID caps, a read-only root with a
small writable workdir, and a wall-clock timeout.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from qabench.sandbox.workdir import write_files
from qabench.types import ExecResult

_TIMEOUT_EXIT = 124


def docker_available() -> bool:
    """True if a Docker CLI is on PATH and the daemon answers."""
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0


class DockerSandbox:
    """Runs files+command inside a one-shot, resource-limited container.

    Defaults are locked down (``--network none``, read-only root). The E2E track
    needs to reach the app under test, so it constructs a sandbox with
    ``network="bridge"`` and an ``host.docker.internal`` host entry.
    """

    def __init__(
        self,
        *,
        memory: str = "512m",
        cpus: str = "1.0",
        pids: int = 256,
        network: str = "none",
        read_only: bool = True,
        extra_hosts: list[str] | None = None,
    ) -> None:
        self.memory = memory
        self.cpus = cpus
        self.pids = pids
        self.network = network
        self.read_only = read_only
        self.extra_hosts = extra_hosts or []

    def run(
        self,
        *,
        image: str,
        files: dict[str, str],
        command: list[str],
        timeout_s: int = 120,
    ) -> ExecResult:
        """Mount ``files`` into ``/work`` and run ``command`` in ``image``."""
        with tempfile.TemporaryDirectory(prefix="qabench-") as tmp:
            workdir = Path(tmp)
            write_files(workdir, files)
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                self.network,
                "--memory",
                self.memory,
                "--cpus",
                self.cpus,
                "--pids-limit",
                str(self.pids),
            ]
            for host in self.extra_hosts:
                docker_cmd += ["--add-host", host]
            if self.read_only:
                docker_cmd += ["--read-only", "--tmpfs", "/tmp:size=64m"]
            docker_cmd += ["-v", f"{workdir}:/work", "-w", "/work", image, *command]
            start = time.perf_counter()
            try:
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return ExecResult(
                    exit_code=_TIMEOUT_EXIT,
                    timed_out=True,
                    duration_s=time.perf_counter() - start,
                )
            return ExecResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_s=time.perf_counter() - start,
            )
