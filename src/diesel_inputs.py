"""Solve the third diesel value from the two most recently edited inputs."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


FIELDS = ('diesel_quantity', 'diesel_rate', 'diesel_advance')


def update_diesel(state, prefix, changed):
    history_key = f'{prefix}_diesel_input_history'
    history = [field for field in state.get(history_key, []) if field != changed]
    history.append(changed)
    state[history_key] = history[-3:]
    def value(field):
        raw = state.get(f'{prefix}_{field}')
        try:
            number = Decimal(str(raw)) if raw is not None else None
            return number if number is not None and number.is_finite() and number >= 0 else None
        except InvalidOperation:
            return None
    if value(changed) is None:
        return
    other = next((field for field in reversed(history[:-1]) if value(field) is not None), None)
    if other is None:
        other = next((field for field in FIELDS if field != changed and value(field) is not None), None)
    if other is None:
        return
    target = next(field for field in FIELDS if field not in (changed, other))
    qty, rate, total = (value(field) for field in FIELDS)
    if target == 'diesel_advance':
        result = qty * rate
    elif target == 'diesel_rate':
        result = total / qty if qty else None
    else:
        result = total / rate if rate else None
    state[f'{prefix}_{target}'] = float(result.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) if result is not None else None
