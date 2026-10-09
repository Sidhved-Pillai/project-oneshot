"""Load current RTGS grouping rules during hot deployment of UPI requests."""
import importlib
from . import rtgs_report

_report = importlib.reload(rtgs_report)
RTGS_REVIEW_COLUMNS = _report.RTGS_REVIEW_COLUMNS
export_rtgs = _report.export_rtgs
normalize_rtgs_records = _report.normalize_rtgs_records
