# Scenario: Save the todo list to a file and check its contents

On the `/export` page there is a control that saves the current todo list to a
file. Preparing the file takes a moment before it is ready.

1. Open `/export`.
2. Start the export.
3. Once it is ready, the file is delivered as a download named `todos.csv`.

Verify that the delivered file actually contains the todos — for example, the
text "Welcome todo" appears inside the file. Inspecting the page alone is not
enough; the check must look at the contents of the file that was produced.
