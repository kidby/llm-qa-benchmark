"""Execution scoring for the E2E/UI track — run the Playwright script.

Unlike the other scorers, this builds its own *network-enabled* Docker sandbox
(the script must reach the app under test) and rewrites ``localhost`` to
``host.docker.internal`` so the container can reach the host's webapp. It is
skipped gracefully when Docker (or the Playwright image) is unavailable.
"""

from __future__ import annotations

import contextlib
import re
import urllib.error
import urllib.request

from qabench.sandbox import PLAYWRIGHT_IMAGE
from qabench.sandbox.docker_exec import DockerSandbox, docker_available
from qabench.types import Sample, ScoreContext, ScoreRow

_CONFIG = """
import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: '.', timeout: 30000, retries: 0 });
"""

_PLAYWRIGHT_BIN = "/pw/node_modules/.bin/playwright"
_HOST = "host.docker.internal"


def _to_host_gateway(text: str) -> str:
    """Rewrite host-local URLs so a container can reach the host's webapp."""
    return re.sub(r"(localhost|127\.0\.0\.1)(?=[:/])", _HOST, text)


def _reset_app(base_url: str) -> None:
    """Best-effort: restore the target app's in-memory state before a test.

    Keeps create-mutation scenarios reproducible. Apps without a ``/api/reset``
    endpoint (e.g. the simple e2e_ui webapp) just 404 — which is ignored. Scoring
    of these mutation tracks should run serially (concurrency=1) so the reset and
    the test it precedes are not interleaved with another test's mutations.
    """
    if not base_url:
        return
    url = base_url.rstrip("/") + "/api/reset"
    # Endpoint absent (e.g. the simple e2e_ui webapp) or unreachable — ignore.
    with contextlib.suppress(urllib.error.URLError, OSError, ValueError):
        urllib.request.urlopen(urllib.request.Request(url, data=b"", method="POST"), timeout=3)


def score_e2e(sample: Sample, parsed: str, ctx: ScoreContext) -> ScoreRow:
    """Run the generated Playwright test against the target app."""
    del ctx  # E2E uses its own networked sandbox, not the shared one
    if not docker_available():
        return {
            "e2e_ran": False,
            "e2e_passed": False,
            "passed": False,
            "e2e_note": "docker unavailable",
        }

    sandbox = DockerSandbox(
        network="bridge",
        read_only=False,  # browsers need to write outside /tmp
        extra_hosts=[f"{_HOST}:host-gateway"],
    )
    base_url = str(sample.payload.get("base_url", ""))
    _reset_app(base_url)  # clean state so create-mutation scenarios are reproducible
    script = _to_host_gateway(parsed.replace("__BASE_URL__", base_url))
    files = {"flow.spec.ts": script, "playwright.config.ts": _CONFIG}
    res = sandbox.run(
        image=PLAYWRIGHT_IMAGE,
        files=files,
        command=[_PLAYWRIGHT_BIN, "test", "--reporter=line"],
        timeout_s=120,
    )
    ran = res.exit_code in (0, 1) and not res.timed_out
    return {
        "e2e_ran": ran,
        "e2e_passed": res.exit_code == 0 and ran,
        "passed": res.exit_code == 0 and ran,
        "e2e_note": "" if ran else (res.stderr or res.stdout)[-200:],
    }
