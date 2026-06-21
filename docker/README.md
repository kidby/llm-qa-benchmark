# Sandbox Images

Generated code executes in a locked-down container (`--network none`, memory/CPU/PID limits,
read-only root filesystem). Build the images once:

```bash
# from the repo root
docker build -f docker/python-runner.Dockerfile     -t qabench-python:latest .
docker build -f docker/node-runner.Dockerfile       -t qabench-node:latest .
docker build -f docker/playwright-runner.Dockerfile -t qabench-playwright:latest .
```

Image tags must match the constants in `qabench/sandbox/__init__.py` (`PYTHON_IMAGE`, `NODE_IMAGE`,
`PLAYWRIGHT_IMAGE`).

When no Docker daemon is available, the harness automatically falls back to a local subprocess
sandbox (`settings.sandbox = "auto"`). Override the choice with `QABENCH_SANDBOX=docker|local` or
the `sandbox` setting.

## Sample Application (E2E Track)

The `e2e_ui` track drives a small standard-library web application in `webapp/`:

```bash
docker compose -f docker/webapp/docker-compose.yml up   # serves http://localhost:8080
```

It exposes a login form and an in-memory todo list with accessible locators (labels, roles,
`data-testid`), enabling robust Playwright tests.

## Advanced Application (e2e_advanced Track)

The `e2e_advanced` track drives a richer standard-library app in `advanced-app/`:

```bash
docker compose -f docker/advanced-app/docker-compose.yml up   # serves http://localhost:8081
```

It adds a multi-page journey (login, dashboard, item detail), a JSON API (`/api/login`,
`/api/todos`), a client-rendered page (`/app`) with an error banner on fetch failure, an async
job (`/api/jobs`, surfaced on `/report`) that completes only after a short delay, an `/export` page
whose `/download/todos.csv` is served as an attachment after a brief delay, a semantic,
axe-clean `/profile` page, and a `/notifications` page that opens a WebSocket to a feed with no
server behind it (so a test must mock the socket via `page.routeWebSocket`). These surfaces let the
advanced samples require reusable structure, fixtures, API integration, network interception,
polling, file-download handling, an accessibility audit, a performance budget, and realtime/WebSocket
interception without the prompt naming any of them.

The Playwright runner image (`playwright-runner.Dockerfile`) installs `@axe-core/playwright`
alongside `@playwright/test` so the accessibility-audit sample can run an axe scan.

The app keeps its todos/jobs in memory and exposes `POST /api/reset` to restore the seed. The E2E
scorer calls it before each test so the create-mutation scenarios (`api_todos`, `fixtures_session`)
are reproducible. Because state is shared across the single app instance, score these E2E tracks
serially (`--concurrency 1` / `QABENCH_CONCURRENCY=1`) so a reset is not interleaved with another
test's mutations.
