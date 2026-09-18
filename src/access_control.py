PRIVATE_RECORD_USERS = {"Manish", "Vijay"}
SELF_DELETE_USERS = {"Ashok", "Manish", "Nitish", "Vijay"}
HIDDEN_LEADERBOARD_USERS = {"Ashok", "Ajit"}
OWN_REPORT_USERS = {"Ashok"}


def can_view_trip_leaderboard(user_name):
    return str(user_name or "").strip() not in HIDDEN_LEADERBOARD_USERS


def scope_report_rows(user_name, records):
    """Limit self-service reporting accounts to records they created."""
    if str(user_name or "").strip() not in OWN_REPORT_USERS:
        return list(records or [])
    return [
        record for record in records or []
        if str(record.get("created_by") or "").strip() == str(user_name or "").strip()
    ]


def can_delete_record(user_name, record):
    """Sid may delete any visible record; approved users may delete only their own."""
    if user_name == "Sid":
        return True
    return user_name in SELF_DELETE_USERS and str(record.get("created_by") or "").strip() == user_name


def can_view_record(user_name, record):
    """Private Records pages show only entries created through that user's login."""
    return user_name not in PRIVATE_RECORD_USERS or str(record.get("created_by") or "").strip() == user_name
