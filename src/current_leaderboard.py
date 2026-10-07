"""Branch leaderboard kept separate for safe Streamlit hot deployment."""

import datetime as dt


def current_month_leaderboard(rows, today, branches=()):
    """Independent of Records filters; deleted/cancelled rows never contribute."""
    active = []
    for row in rows:
        if row.get("is_archived") or row.get("status") == "Cancelled":
            continue
        value = row.get("trip_date")
        try:
            date = value.date() if isinstance(value, dt.datetime) else (
                value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value)[:10])
            )
        except (TypeError, ValueError):
            continue
        if (date.year, date.month) == (today.year, today.month):
            active.append(row)
    result = branch_trip_leaderboard(active, branches)
    return [*result, ("Total", sum(item[1] for item in result), sum(item[2] for item in result))]


def canonical_branch(value):
    original = " ".join(str(value or "").split()).strip()
    return "Vadodara" if original.casefold() in {"vadodra", "vadodara"} else original


def branch_trip_leaderboard(rows, branches=()):
    totals = {canonical_branch(branch).casefold(): (0, 0.0) for branch in branches if canonical_branch(branch)}
    labels = {canonical_branch(branch).casefold(): canonical_branch(branch) for branch in branches if canonical_branch(branch)}
    for row in rows:
        if row.get("report_scope") == "Expense":
            continue
        branch = canonical_branch(row.get("branch")) or "Not specified"
        key = branch.casefold()
        labels.setdefault(key, branch)
        count, revenue = totals.get(key, (0, 0.0))
        try:
            amount = float(row.get("revenue") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        totals[key] = (count + 1, revenue + amount)
    return sorted(
        ((labels[key], count, revenue) for key, (count, revenue) in totals.items()),
        key=lambda item: (-item[2], -item[1], item[0].casefold()),
    )
