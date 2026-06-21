# Scenario: Graceful behaviour when the todos service is unavailable

The `/app` page loads the user's todos from the backend after the page opens. If
that backend request does not succeed, the page should show an error message
instead of a blank list.

Verify this degraded experience: when the todos service is unavailable, the user
sees an error message rather than an empty or broken page. You will need to
reproduce the service being unavailable as part of the test, since it normally
works.

Success is the error message becoming visible on `/app`.
