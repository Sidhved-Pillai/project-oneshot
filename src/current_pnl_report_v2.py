"""Fresh canonical branch grouping on hot deployment."""
import importlib
from . import current_pnl_report
_report = importlib.reload(current_pnl_report)
DIRECT_EXPENSE_COLUMNS = _report.DIRECT_EXPENSE_COLUMNS
branch_pnl_summary = _report.branch_pnl_summary
branch_vehicle_pnl_summary = _report.branch_vehicle_pnl_summary
vehicle_number_pnl_summary = _report.vehicle_number_pnl_summary
export_pnl = _report.export_pnl
