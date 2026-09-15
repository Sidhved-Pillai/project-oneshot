"""Branch leaderboard kept separate for safe Streamlit hot deployment."""


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
