# Scenario: A live notifications badge driven by a server feed

The `/notifications` page shows an unread-notifications badge
(`data-testid="notif-count"`) that starts at 0. The page subscribes to a realtime
feed from the server and updates the badge whenever the server reports a new
unread count.

The feed is provided by a backend service that is not running in this test
environment, so the realtime messages will not arrive on their own. Your test must
simulate the server delivering an update.

1. Open `/notifications`.
2. Arrange for the realtime feed to report 3 unread notifications.
3. Confirm the badge reflects the update.

Verify that the badge reads `3` after the feed reports three unread
notifications.
