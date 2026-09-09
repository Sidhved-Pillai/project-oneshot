"""Branch leaderboard kept separate for safe Streamlit hot deployment."""


def branch_trip_leaderboard(rows, branches=()):
    totals = {str(branch).strip().casefold(): (0, 0.0) for branch in branches if str(branch).strip()}
    labels = {str(branch).strip().casefold(): str(branch).strip() for branch in branches if str(branch).strip()}
    for row in rows:
        if row.get("report_scope") == "Expense":
            continue
        branch = str(row.get("branch") or "").strip() or "Not specified"
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
