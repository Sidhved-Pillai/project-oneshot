import datetime as dt
import math
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from src.pnl_report import BRANCH_PNL_COLUMNS, branch_pnl_summary, vehicle_number_pnl_summary, export_pnl


@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), '-Infinity', 'NaN', None, ''])
@pytest.mark.parametrize('mode', ['Both', 'Vehicle No. Wise'])
def test_invalid_optional_amount_cannot_erase_valid_expense_and_profit(invalid, mode):
    trips = [{'branch':'Wada', 'vehicle_number':'MH12AB1234', 'ownership_type':'Own',
              'revenue':10000, 'upi':1000, 'diesel_advance':2000,
              'dtr_data':{'Toll Expense':500, 'Repairs & Maintenance':invalid}},
             {'branch':'Pune', 'vehicle_number':'MH12AB5678', 'ownership_type':'Outside',
              'revenue':20000, 'transporter_freight':15000}]
    expenses = [{'branch':'Wada', 'vehicle_number':'MH12AB1234', 'amount':500,
                 'categories':{'Salary':invalid, 'Office & General expenses':500}}]
    function = branch_pnl_summary if mode == 'Both' else vehicle_number_pnl_summary
    rows = function(trips, expenses)
    assert rows[-1]['Total Revenue'] == 30000
    assert rows[-1]['Expense'] == 19000
    assert rows[-1]['Profit'] == 11000
    for column in BRANCH_PNL_COLUMNS[1:]:
        assert all(math.isfinite(row[column]) for row in rows)
        assert Decimal(str(rows[-1][column])) == sum(Decimal(str(row[column])) for row in rows[:-1])
    workbook = load_workbook(BytesIO(export_pnl(trips, expenses, dt.date(2026,10,1), dt.date(2026,10,27), mode)))
    cells = [cell.value for row in workbook['P&L'] for cell in row]
    assert 19000 in cells and 11000 in cells


def test_total_uses_displayed_branch_currency_values():
    trips = [{'branch':branch, 'ownership_type':'Own', 'revenue':1.005, 'upi':0.004,
              'diesel_advance':0.004} for branch in ('Wada','Pune')]
    rows = branch_pnl_summary(trips, [])
    for row in rows:
        assert row['Expense'] == 0
        assert row['Profit'] == row['Total Revenue']
    assert rows[-1]['Total Revenue'] == sum(row['Total Revenue'] for row in rows[:-1])
