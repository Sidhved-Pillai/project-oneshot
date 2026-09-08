def can_delete_record(user_name, record):
    """Sid may delete any visible record; Manish may delete only his own."""
    if user_name == "Sid":
        return True
    return user_name == "Manish" and str(record.get("created_by") or "").strip() == "Manish"

