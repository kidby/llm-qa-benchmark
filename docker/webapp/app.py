"""A tiny self-contained web app used as the target for the E2E/UI track.

Stdlib only (no framework) so it builds fast and has no dependencies. Serves a
login form, a welcome screen, and an in-memory todo list. Accessible locators
(labels, roles, data-testid) are provided so robust tests are possible.
"""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

USER, PASSWORD = "demo", "password123"
_TODOS: list[str] = []

_LOGIN_PAGE = """<!doctype html>
<title>Login</title>
<main>
  <h1>Sign in</h1>
  <form method="post" action="/login">
    <label for="u">Username</label>
    <input id="u" name="username" aria-label="Username" />
    <label for="p">Password</label>
    <input id="p" name="password" type="password" aria-label="Password" />
    <button type="submit">Log in</button>
  </form>
  {error}
</main>
"""


def _welcome_page() -> str:
    items = "".join(
        f'<li data-testid="todo-item">{html.escape(t)}</li>' for t in _TODOS
    )
    return f"""<!doctype html>
<title>Welcome</title>
<main>
  <h1>Welcome, {USER}</h1>
  <form method="post" action="/todos">
    <label for="t">New todo</label>
    <input id="t" name="title" aria-label="New todo" />
    <button type="submit">Add</button>
  </form>
  <ul aria-label="Todo list">{items}</ul>
</main>
"""


class Handler(BaseHTTPRequestHandler):
    """Minimal request handler for the login + todo flow."""

    def _send(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path.startswith("/welcome"):
            self._send(_welcome_page())
        else:
            self._send(_LOGIN_PAGE.format(error=""))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        if self.path == "/login":
            if form.get("username") == [USER] and form.get("password") == [PASSWORD]:
                self._send(_welcome_page())
            else:
                error = '<p role="alert">Invalid credentials</p>'
                self._send(_LOGIN_PAGE.format(error=error), status=401)
        elif self.path == "/todos":
            title = (form.get("title") or [""])[0].strip()
            if title:
                _TODOS.append(title)
            self._send(_welcome_page())
        else:
            self._send("not found", status=404)

    def log_message(self, *args: object) -> None:  # noqa: D102 (silence access log)
        return


def main() -> None:
    """Run the app on port 8080."""
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
