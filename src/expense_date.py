"""Retain Nikhat's last successfully saved expense date across fresh forms."""


def seed_expense_date(state, user, prefix):
    if user == 'Nikhat' and 'nikhat_last_expense_date' in state:
        state.setdefault(f'{prefix}_date', state['nikhat_last_expense_date'])


def remember_expense_date(state, user, date):
    if user == 'Nikhat':
        state['nikhat_last_expense_date'] = date
