# Scenario: Verify the todos service contract directly

The app exposes a todos service at `/api/todos`. Verify its behaviour directly at
the service level, without going through the browser UI:

1. Create a new todo named "Call dentist" by sending it to the todos service.
   Creating a todo responds with HTTP 201.
2. Fetch the list of todos from the service and confirm "Call dentist" is present.

The test should exercise the service endpoints directly rather than clicking
through pages.
