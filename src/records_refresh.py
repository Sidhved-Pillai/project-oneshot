"""Replace a saved trip in an existing Records snapshot."""


def replace_saved_record(rows, request_number, fetch_record, project_records):
    fresh = fetch_record(request_number)
    if not fresh or fresh.get('is_archived') or fresh.get('status') == 'Cancelled':
        return list(rows), None
    fresh = project_records([fresh])[0]
    return [fresh if row['request_number'] == request_number else row for row in rows], fresh
