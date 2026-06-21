"""Target web app for the ``e2e_advanced`` track.

Stdlib-only, so it builds fast and has no dependencies. It deliberately exposes
the surfaces each advanced scenario needs, without ever naming the technique:

- multi-page, server-rendered journey (login -> dashboard -> item detail) so a
  Page Object Model is the natural structure;
- a seeded, cookie-authenticated area so a shared fixture removes repeated setup;
- a JSON API (``/api/login``, ``/api/todos``) for direct API integration tests;
- a client-rendered page (``/app``) that fetches todos and shows an error banner
  on failure, so a network-issue test must intercept the request;
- an async job (``/api/jobs``) whose status flips to ``done`` only after a delay,
  surfaced on ``/report``, so verifying it requires waiting/polling;
- an ``/export`` page whose ``/download/todos.csv`` is prepared after a short delay
  and served as an attachment, so verifying its contents requires handling the
  browser download rather than reading the DOM;
- a clean, semantic ``/profile`` page so an accessibility audit can assert no
  serious violations;
- fast, server-rendered pages so a performance check can read load timings;
- a ``/notifications`` page that opens a WebSocket to a feed with no server behind
  it, so the unread badge only updates if a test mocks the socket
  (``page.routeWebSocket``).
"""

from __future__ import annotations

import html
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

USER, PASSWORD, TOKEN = "demo", "password123", "demo-token"
SESSION_COOKIE = "session=demo-token"

# Catalogue for the dashboard / detail pages and the seeded todo.
ITEMS = {
    "1": {"title": "Wireless Keyboard", "price": "49.00"},
    "2": {"title": "USB-C Hub", "price": "29.50"},
    "3": {"title": "Laptop Stand", "price": "79.99"},
}
_TODOS: list[str] = ["Welcome todo"]
# Jobs map an id to the epoch time at which they finish.
_JOBS: dict[str, float] = {}
_JOB_SECONDS = 3.0
# Seconds the export takes to "prepare" before the file is ready to download.
_EXPORT_SECONDS = 2.0
_PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    "<title>{title}</title></head><body><main>{body}</main></body></html>"
)


def _page(title: str, body: str) -> str:
    return _PAGE.format(title=html.escape(title), body=body)


def _login_page(error: str = "") -> str:
    return _page(
        "Sign in",
        f"""
        <h1>Sign in</h1>
        <form method="post" action="/login">
          <label for="u">Username</label>
          <input id="u" name="username" aria-label="Username" />
          <label for="p">Password</label>
          <input id="p" name="password" type="password" aria-label="Password" />
          <button type="submit">Log in</button>
        </form>{error}""",
    )


def _dashboard_page() -> str:
    links = "".join(
        f'<li><a href="/items/{i}" data-testid="item-link">{html.escape(it["title"])}</a></li>'
        for i, it in ITEMS.items()
    )
    return _page(
        "Dashboard",
        f'<h1>Dashboard</h1><nav><a href="/report">Reports</a></nav>'
        f'<ul aria-label="Items">{links}</ul>',
    )


def _item_page(item_id: str) -> str | None:
    item = ITEMS.get(item_id)
    if item is None:
        return None
    return _page(
        item["title"],
        f'<h1 data-testid="item-title">{html.escape(item["title"])}</h1>'
        f'<p data-testid="item-price">${html.escape(item["price"])}</p>'
        f'<a href="/dashboard">Back</a>',
    )


_APP_PAGE = _page(
    "Todos",
    """
    <h1>Your todos</h1>
    <ul aria-label="Todo list" data-testid="todo-list"></ul>
    <p data-testid="error-banner" role="alert" hidden>Could not load your todos.</p>
    <script>
      fetch('/api/todos')
        .then(r => { if (!r.ok) throw new Error('bad status'); return r.json(); })
        .then(items => {
          const ul = document.querySelector('[data-testid="todo-list"]');
          for (const t of items.todos) {
            const li = document.createElement('li');
            li.textContent = t;
            li.setAttribute('data-testid', 'todo-item');
            ul.appendChild(li);
          }
        })
        .catch(() => {
          document.querySelector('[data-testid="error-banner"]').hidden = false;
        });
    </script>""",
)

_REPORT_PAGE = _page(
    "Report",
    """
    <h1>Reports</h1>
    <button data-testid="generate">Generate report</button>
    <p data-testid="report-status">idle</p>
    <script>
      const status = document.querySelector('[data-testid="report-status"]');
      document.querySelector('[data-testid="generate"]').addEventListener('click', async () => {
        status.textContent = 'processing';
        const { id } = await (await fetch('/api/jobs', { method: 'POST' })).json();
        const poll = setInterval(async () => {
          const job = await (await fetch('/api/jobs/' + id)).json();
          if (job.status === 'done') { clearInterval(poll); status.textContent = 'done'; }
        }, 500);
      });
    </script>""",
)


_NOTIFICATIONS_PAGE = _page(
    "Notifications",
    """
    <h1>Notifications</h1>
    <p>Unread: <span data-testid="notif-count">0</span></p>
    <script>
      // The badge updates from a realtime feed. No feed server runs here, so a
      // test must intercept/mock the WebSocket to drive the unread count.
      const badge = document.querySelector('[data-testid="notif-count"]');
      const ws = new WebSocket(`ws://${location.host}/feed`);
      ws.onmessage = (e) => { badge.textContent = String(JSON.parse(e.data).unread); };
    </script>""",
)


_EXPORT_PAGE = _page(
    "Export",
    """
    <h1>Export your todos</h1>
    <p>Your todos can be saved to a file. The file is prepared on request and may
       take a moment before it is ready.</p>
    <a id="export-link" data-testid="export" href="/download/todos.csv" download="todos.csv">
      Export todos
    </a>""",
)


def _profile_page() -> str:
    return _page(
        "Your profile",
        """
        <nav aria-label="Primary"><a href="/dashboard">Dashboard</a></nav>
        <h1>Your profile</h1>
        <form>
          <label for="name">Full name</label>
          <input id="name" name="name" value="Demo User" />
          <label for="email">Email address</label>
          <input id="email" name="email" type="email" value="demo@example.com" />
          <button type="submit">Save changes</button>
        </form>""",
    )


def _todos_csv() -> str:
    """The current todos as a small CSV document."""
    return "todo\n" + "\n".join(_TODOS) + "\n"


class Handler(BaseHTTPRequestHandler):
    """Routes for the advanced E2E target app."""

    def _send(self, body: str, status: int = 200, ctype: str = "text/html") -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, payload: dict[str, object], status: int = 200) -> None:
        self._send(json.dumps(payload), status=status, ctype="application/json")

    def _download_csv(self) -> None:
        # The file is "prepared" before it is ready, so a test must wait for the
        # browser download rather than asserting immediately.
        time.sleep(_EXPORT_SECONDS)
        body = _todos_csv().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="todos.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        return SESSION_COOKIE in self.headers.get("Cookie", "")

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        path = urlparse(self.path).path
        if path == "/api/todos":
            self._json({"todos": list(_TODOS)})
        elif path.startswith("/api/jobs/"):
            self._job_status(path.rsplit("/", 1)[-1])
        elif path == "/dashboard":
            self._send(_dashboard_page()) if self._authed() else self._send(
                _login_page(), status=401
            )
        elif path.startswith("/items/"):
            page = _item_page(path.rsplit("/", 1)[-1])
            self._send(page) if page else self._send("not found", status=404)
        elif path == "/app":
            self._send(_APP_PAGE)
        elif path == "/report":
            self._send(_REPORT_PAGE)
        elif path == "/export":
            self._send(_EXPORT_PAGE)
        elif path == "/download/todos.csv":
            self._download_csv()
        elif path == "/profile":
            self._send(_profile_page())
        elif path == "/notifications":
            self._send(_NOTIFICATIONS_PAGE)
        else:
            self._send(_login_page())

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        if path == "/login":
            self._form_login(parse_qs(raw))
        elif path == "/api/login":
            self._api_login(raw)
        elif path == "/api/todos":
            self._api_create_todo(raw)
        elif path == "/api/jobs":
            self._start_job()
        elif path == "/api/reset":
            self._reset()
        else:
            self._send("not found", status=404)

    def _reset(self) -> None:
        # Restore the in-memory store to its seed so each scored test starts clean
        # (the harness calls this before every E2E run; see qabench/scoring/e2e.py).
        _TODOS[:] = ["Welcome todo"]
        _JOBS.clear()
        self._json({"ok": True})

    def _form_login(self, form: dict[str, list[str]]) -> None:
        if form.get("username") == [USER] and form.get("password") == [PASSWORD]:
            encoded = _dashboard_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Set-Cookie", SESSION_COOKIE + "; Path=/")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        else:
            self._send(_login_page('<p role="alert">Invalid credentials</p>'), status=401)

    def _api_login(self, raw: str) -> None:
        body = _parse_json(raw)
        if body.get("username") == USER and body.get("password") == PASSWORD:
            self._json({"token": TOKEN})
        else:
            self._json({"error": "invalid credentials"}, status=401)

    def _api_create_todo(self, raw: str) -> None:
        body = _parse_json(raw)
        title = str(body.get("title", "")).strip()
        if not title:
            self._json({"error": "title required"}, status=400)
            return
        _TODOS.append(title)
        self._json({"title": title}, status=201)

    def _start_job(self) -> None:
        job_id = str(len(_JOBS) + 1)
        _JOBS[job_id] = time.monotonic() + _JOB_SECONDS
        self._json({"id": job_id}, status=201)

    def _job_status(self, job_id: str) -> None:
        finish = _JOBS.get(job_id)
        if finish is None:
            self._json({"error": "unknown job"}, status=404)
            return
        done = time.monotonic() >= finish
        self._json({"status": "done" if done else "running", "result": "42" if done else None})

    def log_message(self, *args: object) -> None:  # noqa: D102 (silence access log)
        return


def _parse_json(raw: str) -> dict[str, object]:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main() -> None:
    """Run the advanced app on port 8081."""
    ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()


if __name__ == "__main__":
    main()
