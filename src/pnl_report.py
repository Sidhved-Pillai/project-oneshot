from io import BytesIO
import json

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


DIRECT_EXPENSE_COLUMNS = [
    "Route expense", "Bill discounting", "Salary", "Driver's salary", "Rent",
    "Office & General expenses", "Conveyance", "EMI", "Insurance", "Vehicle Tax",
    "Repair and maintenance", "Interest",
]
REPORT_EXPENSE_COLUMNS = [*DIRECT_EXPENSE_COLUMNS, "Passing expense"]


def pnl_summary(trip_rows, expense_rows):
    revenue = sum(float(row.get("revenue") or 0) for row in trip_rows)
    transporter = sum(float(row.get("transporter_freight") or 0) for row in trip_rows)
    categories = {name: 0.0 for name in REPORT_EXPENSE_COLUMNS}
    for row in expense_rows:
        for name, value in row.get("categories", {}).items():
            if name in categories:
                categories[name] += float(value or 0)
    direct_total = sum(categories.values())
    gross = revenue - transporter
    return [
        {"Particular": "Revenue", "Amount": revenue},
        {"Particular": "Transporter Freight", "Amount": -transporter},
        {"Particular": "Gross Contribution", "Amount": gross},
        *({"Particular": name, "Amount": -amount} for name, amount in categories.items()),
        {"Particular": "Total Direct Expenses", "Amount": -direct_total},
        {"Particular": "Net Profit / (Loss)", "Amount": gross - direct_total},
    ]


def _amount(row, field):
    if isinstance(row, str):
        try:
            row = json.loads(row)
        except (TypeError, ValueError):
            row = {}
    if not isinstance(row, dict):
        row = {}
    try:
        return float(row.get(field) or 0)
    except (TypeError, ValueError):
        return 0.0


def _category_total(expense_rows, *names):
    return sum(
        _amount(row.get("categories", {}), name)
        for row in expense_rows
        for name in names
    )


def vehicle_pnl_summary(trip_rows, expense_rows, ownership):
    """Return the compact operations P&L requested for own/outside vehicles."""
    ownership = str(ownership or "Both")
    own_trips = [row for row in trip_rows if str(row.get("ownership_type") or "").strip().lower().startswith("own")]
    outside_trips = [row for row in trip_rows if str(row.get("ownership_type") or "").strip().lower().startswith("outside")]
    own_vehicles = {str(row.get("vehicle_number") or "").strip().casefold() for row in own_trips} - {""}
    outside_vehicles = {str(row.get("vehicle_number") or "").strip().casefold() for row in outside_trips} - {""}
    if own_trips and outside_trips:
        own_expenses = [row for row in expense_rows if str(row.get("vehicle_number") or "").strip().casefold() in own_vehicles]
        outside_expenses = [row for row in expense_rows if str(row.get("vehicle_number") or "").strip().casefold() in outside_vehicles]
    else:
        own_expenses = outside_expenses = expense_rows

    def own_rows():
        revenue = sum(_amount(row, "revenue") for row in own_trips)
        route = sum(_amount(row, "upi") for row in own_trips)
        toll = sum(_amount(row.get("dtr_data", {}), "Toll Expense") for row in own_trips)
        diesel = sum(_amount(row, "diesel_advance") for row in own_trips)
        driver_salary = _category_total(own_expenses, "Driver's salary")
        emi = _category_total(own_expenses, "EMI")
        insurance = _category_total(own_expenses, "Insurance")
        vehicle_tax = _category_total(own_expenses, "Vehicle Tax")
        repairs = sum(_amount(row.get("dtr_data", {}), "Repairs & Maintenance") for row in own_trips)
        repairs += _category_total(own_expenses, "Repair and maintenance")
        expenses = route + toll + diesel + driver_salary + emi + insurance + vehicle_tax + repairs
        return [
            {"Particular": "Revenue freight", "Amount": revenue},
            {"Particular": "Route expenses (UPI)", "Amount": -route},
            {"Particular": "Toll charges", "Amount": -toll},
            {"Particular": "Diesel amount", "Amount": -diesel},
            {"Particular": "Driver's salary", "Amount": -driver_salary},
            {"Particular": "EMI", "Amount": -emi},
            {"Particular": "Insurance", "Amount": -insurance},
            {"Particular": "Vehicle Tax", "Amount": -vehicle_tax},
            {"Particular": "Repair and maintenance", "Amount": -repairs},
            {"Particular": "Net Profit / (Loss)", "Amount": revenue - expenses},
        ]

    def outside_rows():
        revenue = sum(_amount(row, "revenue") for row in outside_trips)
        transporter = sum(_amount(row, "transporter_freight") for row in outside_trips)
        additional = sum(_amount(row, "amount") for row in outside_expenses)
        return [
            {"Particular": "Revenue", "Amount": revenue},
            {"Particular": "Transporter Freight", "Amount": -transporter},
            {"Particular": "Additional expenses", "Amount": -additional},
            {"Particular": "Net Profit / (Loss)", "Amount": revenue - transporter - additional},
        ]

    own = own_rows()
    outside = outside_rows()
    if ownership == "Own":
        return own
    if ownership == "Outside":
        return outside
    own_values = {row["Particular"]: row["Amount"] for row in own}
    outside_values = {row["Particular"]: row["Amount"] for row in outside}
    return [
        {"Particular": "Revenue freight", "Amount": own_values["Revenue freight"] + outside_values["Revenue"]},
        *own[1:-1],
        {"Particular": "Transporter Freight", "Amount": outside_values["Transporter Freight"]},
        {"Particular": "Additional expenses", "Amount": outside_values["Additional expenses"]},
        {
            "Particular": "Net Profit / (Loss)",
            "Amount": own_values["Net Profit / (Loss)"] + outside_values["Net Profit / (Loss)"],
        },
    ]


def export_pnl(trip_rows, expense_rows, start_date, end_date, ownership=None):
    rows = vehicle_pnl_summary(trip_rows, expense_rows, ownership) if ownership else pnl_summary(trip_rows, expense_rows)
    frame = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="P&L", startrow=2)
        ws = writer.book["P&L"]
        ws["A1"] = f"Profit & Loss | {start_date:%d-%m-%Y} to {end_date:%d-%m-%Y}"
        ws["A1"].font = Font(size=14, bold=True, color="17324D")
        ws.merge_cells("A1:B1")
        fill = PatternFill("solid", fgColor="0F766E")
        for cell in ws[3]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(1)].width = 32
        ws.column_dimensions[get_column_letter(2)].width = 18
        for cell in ws["B"][3:]:
            cell.number_format = '₹#,##0.00;[Red]-₹#,##0.00'
    return output.getvalue()
