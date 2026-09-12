PRIVATE_RECORD_USERS = {"Manish", "Vijay"}
SELF_DELETE_USERS = {"Manish", "Nitish", "Vijay"}


def can_delete_record(user_name, record):
    """Sid may delete any visible record; approved users may delete only their own."""
    if user_name == "Sid":
        return True
    return user_name in SELF_DELETE_USERS and str(record.get("created_by") or "").strip() == user_name


def can_view_record(user_name, record):
    """Private Records pages show only entries created through that user's login."""
    return user_name not in PRIVATE_RECORD_USERS or str(record.get("created_by") or "").strip() == user_name
