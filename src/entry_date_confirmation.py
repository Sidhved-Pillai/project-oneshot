"""Confirm dates that are easy to save under the wrong reporting period."""


def entry_date_requires_confirmation(date, today):
    return bool(date and (date > today or (date.year, date.month) != (today.year, today.month)))
