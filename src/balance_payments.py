"""Permissions and identifiers for separately requested trip balance payments."""

BALANCE_PAYMENT_USERS = {"Ashok", "Ajit", "Nitish", "Sid", "Vinod", "Nikhil"}
BALANCE_PREFIX = "BALANCE:"


def can_send_balance(user, row):
    if user not in BALANCE_PAYMENT_USERS or row.get("report_scope") == "Expense":
        return False
    if row.get("is_archived") or row.get("status") == "Cancelled":
        return False
    branch = str(row.get("branch") or "").strip().casefold()
    if user == "Ashok":
        return branch in {"vadodara", "vadodra", "baroda"}
    if user == "Nitish":
        return branch == "pune"
    return True
