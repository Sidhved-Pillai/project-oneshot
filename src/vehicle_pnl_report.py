"""Hot-reload-safe entry points for the vehicle-number-wise P&L."""

import importlib

from . import pnl_report as _pnl_report


_pnl_report = importlib.reload(_pnl_report)

vehicle_number_pnl_summary = _pnl_report.vehicle_number_pnl_summary
export_pnl = _pnl_report.export_pnl
