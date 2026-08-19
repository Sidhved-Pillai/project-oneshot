from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


DIRECT_EXPENSE_COLUMNS = [
    "Route expense", "Bill discounting", "Salary", "Driver's salary", "Rent",
    "Office & General expenses", "Conveyance", "EMI", "Insurance", "Vehicle Tax",
    "Repair and maintenance", "Interest",
]


def pnl_summary(trip_rows, expense_rows):
    revenue = sum(float(row.get("revenue") or 0) for row in trip_rows)
    transporter = sum(float(row.get("transporter_freight") or 0) for row in trip_rows)
    categories = {name: 0.0 for name in DIRECT_EXPENSE_COLUMNS}
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


def export_pnl(trip_rows, expense_rows, start_date, end_date):
    frame = pd.DataFrame(pnl_summary(trip_rows, expense_rows))
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
