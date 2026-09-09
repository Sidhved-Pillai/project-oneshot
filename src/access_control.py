PRIVATE_RECORD_USERS = {"Manish", "Vijay"}


def can_delete_record(user_name, record):
    """Sid may delete any visible record; Manish may delete only his own."""
    if user_name == "Sid":
        return True
    return user_name == "Manish" and str(record.get("created_by") or "").strip() == "Manish"


def can_view_record(user_name, record):
    """Private Records pages show only entries created through that user's login."""
    return user_name not in PRIVATE_RECORD_USERS or str(record.get("created_by") or "").strip() == user_name
