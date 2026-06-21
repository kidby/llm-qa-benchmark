# Scenario: Several checks that all need the same signed-in state

A signed-in session already has one todo present ("Welcome todo"). Write a test
file with multiple independent checks that each begin from that same authenticated,
seeded starting point. Set the shared starting state up once and reuse it across
the checks rather than repeating the sign-in steps in every check.

Checks to cover:
1. The todo list on `/app` shows the pre-existing "Welcome todo".
2. After adding a todo named "Pay rent" via the API, the list shows both the
   pre-existing "Welcome todo" and the newly added "Pay rent".

Both checks must each start from the same signed-in, seeded state.
