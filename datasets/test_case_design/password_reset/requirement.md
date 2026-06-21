# Requirement: Password reset

Users can reset their password from the login page.

- The user enters their email and clicks "Send reset link".
- If the email belongs to a registered account, a reset link valid for 30 minutes
  is emailed. For privacy, the UI shows the same confirmation regardless of whether
  the email is registered.
- The reset link opens a form to enter a new password twice.
- A new password must be 8–64 characters, contain at least one letter and one digit,
  and must not equal the previous password.
- Reset links are single-use and expire after 30 minutes or after a successful reset.
- After 5 failed reset attempts from one IP within 15 minutes, further attempts are
  rate-limited for 15 minutes.
