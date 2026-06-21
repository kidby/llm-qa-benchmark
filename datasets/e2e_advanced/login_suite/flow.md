# Scenario: A suite of tests for the sign-in page

Write a suite of several independent tests for the sign-in page at `/` (the login
form takes a username and password; valid credentials are `demo` / `password123`).

Cover at least these cases, each as its own test:
1. Signing in with valid credentials reaches the dashboard.
2. Signing in with a wrong password shows an error and stays on the sign-in page.
3. Signing in with an empty password shows an error.
4. The sign-in form exposes username and password fields and a submit control.
5. After signing in, the dashboard lists items.

The tests will grow over time, so organise the suite so the sign-in interaction is
defined once and reused across the tests rather than repeated in each one.
