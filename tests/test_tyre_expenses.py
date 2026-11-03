import datetime as dt
from io import BytesIO
from openpyxl import load_workbook
from src.pnl_report import branch_pnl_summary, vehicle_number_pnl_summary, vehicle_pnl_summary, export_pnl


def test_tyre_expenses_are_counted_once_in_reports_and_exports():
    trip = {'branch':'Wada','vehicle_number':'TEST1234','ownership_type':'Own','revenue':10000}
    expense = {'branch':'Wada','vehicle_number':'TEST1234','ownership_type':'Own',
               'amount':2500,'categories':{'Tyre Purchased':2500}}
    for report in (branch_pnl_summary, vehicle_number_pnl_summary):
        total = report([trip], [expense])[-1]
        assert total['Tyre Purchased'] == 2500
        assert total['Expense'] == 2500 and total['Profit'] == 7500
    rows = {r['Particular']:r['Amount'] for r in vehicle_pnl_summary([trip],[expense],'Own')}
    assert rows['Tyre Purchased'] == -2500
    assert rows['Net Profit / (Loss)'] == 7500
    workbook = load_workbook(BytesIO(export_pnl([trip],[expense],dt.date(2026,11,1),dt.date(2026,11,3),'Both')))
    assert any(cell.value == 'Tyre Purchased' for row in workbook.active for cell in row)
