"""Refresh statement labels for confirmed opening balances."""
import importlib
from . import balance_bill
_bill = importlib.reload(balance_bill)
bill_group_key = _bill.bill_group_key
make_bill = _bill.make_bill
totals = _bill.totals
render_bill_html = _bill.render_bill_html
export_bill = _bill.export_bill
