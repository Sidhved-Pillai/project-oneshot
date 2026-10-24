from pathlib import Path

from src.vijay_finance import project_vijay_records, vijay_finance_summary
from src.pnl_report import branch_pnl_summary, vehicle_pnl_summary


ROOT = Path(__file__).resolve().parents[1]


def vijay_trip(**changes):
    row = {
        "created_by": "Vijay", "report_scope": "Both", "branch": "Andheri",
        "ownership_type": "Outside", "revenue": 10_000, "transporter_freight": 8_000,
        "upi": 500, "diesel_advance": 1_000, "cash_advance": 250, "rtgs_advance": 750,
        "dtr_data": {"Toll Expense": 200, "Billtee": 300, "Own/Outside Veh.": "Outside"},
    }
    row.update(changes)
    return row


def test_vijay_finance_separates_advance_expense_and_profit():
    assert vijay_finance_summary(10_000, 500, 1_000, 250, 750, 200, 300) == {
        "total_expense": 3_000,
        "total_advance": 2_800,
        "profit_loss": 7_000,
    }


def test_all_saved_vijay_trips_are_projected_as_own_without_mutating_source():
    source = vijay_trip()
    projected = project_vijay_records([source])[0]
    assert source["ownership_type"] == "Outside"
    assert projected["ownership_type"] == "Own"
    assert projected["transporter_freight"] == 0
    assert projected["total_advance"] == 2_800
    assert projected["amount"] == 3_000
    assert projected["balance_amount"] == 7_000
    assert projected["dtr_data"]["Own/Outside Veh."] == "Own"
    assert projected["dtr_data"]["Transporter Freight"] == 0


def test_projection_does_not_change_other_users_or_direct_expenses():
    other = vijay_trip(created_by="Ashok")
    expense = vijay_trip(report_scope="Expense")
    result = project_vijay_records([other, expense])
    assert result[0] == other
    assert result[1] == expense


def test_vijay_cash_rtgs_billtee_and_toll_reach_branch_report():
    trip = project_vijay_records([vijay_trip()])[0]
    andheri = branch_pnl_summary([trip], [])[0]
    assert andheri["Revenue-Own"] == 10_000
    assert andheri["Transporter Freight"] == 0
    assert andheri["UPI"] == 500
    assert andheri["Diesel"] == 1_000
    assert andheri["Toll"] == 200
    assert andheri["Extra Exp"] == 1_300
    assert andheri["Expense"] == 3_000
    assert andheri["Profit"] == 7_000


def test_vijay_other_payments_reach_own_vehicle_report():
    rows = vehicle_pnl_summary(project_vijay_records([vijay_trip()]), [], "Own")
    values = {row["Particular"]: row["Amount"] for row in rows}
    assert values["Other trip payments"] == -1_300
    assert values["Net Profit / (Loss)"] == 7_000


def test_shyam_new_entry_and_vijay_ui_contracts_are_present():
    source = (ROOT / "app.py").read_text()
    assert 'st.tabs(["New Entry", "Direct Expenses", "Records", "Generate Reports", "Logs"])' in source
    assert '"Review DTR" if current_user == "Shyam"' not in source
    assert 'st.session_state[f"{prefix}_ownership_type"] = "Own"' in source
    for label in ("UPI", "Diesel", "Cash", "RTGS", "Toll Expense", "Billtee"):
        assert f'("{label}",' in source
    assert 'summary[0].metric("Total Expense"' in source
    assert 'summary[1].metric("Total Advance"' in source
