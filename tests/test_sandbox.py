from __future__ import annotations

import pytest
from qabench.config import Settings
from qabench.sandbox import LocalSandbox, get_sandbox
from qabench.sandbox.local_exec import _resolve


def test_local_sandbox_runs_python() -> None:
    sb = LocalSandbox()
    res = sb.run(
        image="ignored",
        files={"hello.py": "print('hi')"},
        command=["python", "hello.py"],
    )
    assert res.ok
    assert "hi" in res.stdout


def test_local_sandbox_reports_failure() -> None:
    sb = LocalSandbox()
    res = sb.run(
        image="ignored",
        files={"boom.py": "raise SystemExit(3)"},
        command=["python", "boom.py"],
    )
    assert res.exit_code == 3
    assert not res.ok


def test_local_sandbox_times_out() -> None:
    sb = LocalSandbox()
    res = sb.run(
        image="ignored",
        files={"slow.py": "import time; time.sleep(5)"},
        command=["python", "slow.py"],
        timeout_s=1,
    )
    assert res.timed_out
    assert not res.ok


def test_resolve_maps_python_to_interpreter() -> None:
    import sys

    assert _resolve(["python", "x.py"])[0] == sys.executable
    assert _resolve([]) == []


def test_get_sandbox_local() -> None:
    sb = get_sandbox(Settings(sandbox="local"))
    assert isinstance(sb, LocalSandbox)


@pytest.mark.docker
def test_docker_sandbox_smoke() -> None:
    from qabench.sandbox import DockerSandbox
    from qabench.sandbox.docker_exec import docker_available

    if not docker_available():
        pytest.skip("docker not available")
    sb = DockerSandbox()
    res = sb.run(
        image="python:3.11-slim",
        files={"hello.py": "print('hi')"},
        command=["python", "hello.py"],
    )
    assert res.ok
    assert "hi" in res.stdout
