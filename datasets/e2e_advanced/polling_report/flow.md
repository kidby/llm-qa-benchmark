# Scenario: Wait for a report that is not generated instantly

On the `/report` page there is a "Generate report" button and a status indicator.

1. Open `/report`.
2. Click "Generate report".
3. The report does not finish immediately; the server processes it for a few
   seconds before it is ready. The status indicator becomes "done" once it
   finishes.

Verify that the finished report is reflected in the status indicator. The test
must account for the processing delay rather than checking the status the instant
the button is clicked.
