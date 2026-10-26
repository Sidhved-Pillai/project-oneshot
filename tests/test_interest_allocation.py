from decimal import Decimal
from io import BytesIO
import datetime as dt

from openpyxl import load_workbook
from src.pnl_report import branch_pnl_summary, export_pnl, vehicle_number_pnl_summary


def test_both_interest_split_updates_profit_and_excel_without_changing_source():
    expenses = [{"branch": "Andheri", "categories": {"Interest": 303659}}]
    rows = branch_pnl_summary([], expenses)
    assert {row["Branch"] for row in rows[:-1]} == {"Andheri", "Pune", "Vadodara", "Wada"}
    for row in rows[:-1]:
        assert row["Interest"] == row["Expense"] == 75914.75
        assert row["Profit"] == -75914.75
    assert rows[-1]["Interest"] == 303659
    assert expenses[0]["categories"]["Interest"] == 303659
    workbook = load_workbook(BytesIO(export_pnl([], expenses, dt.date(2026,10,1), dt.date(2026,10,26), "Both")))
    sheet = workbook["P&L"]
    assert sum(cell.value == 75914.75 for row in sheet for cell in row) >= 4


def test_fractional_paise_preserves_report_total_and_vehicle_view_is_unchanged():
    expenses = [{"branch": "Pune", "vehicle_number": "MH12AB1234", "amount": 100.01,
                 "categories": {"Interest": 100.01}}]
    rows = branch_pnl_summary([], expenses)
    assert sum(Decimal(str(row["Interest"])) for row in rows[:-1]) == Decimal('100.01')
    vehicle_rows = vehicle_number_pnl_summary([], expenses)
    assert len(vehicle_rows) == 2
    assert vehicle_rows[0]["Interest"] == 100.01
