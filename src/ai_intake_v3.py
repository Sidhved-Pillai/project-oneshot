"""Refresh Saint-Gobain multi-invoice extraction and driver fields."""
import importlib
from . import ai_intake
_intake = importlib.reload(ai_intake)
extract_intake = _intake.extract_intake
merge_same_trip_intake_rows = _intake.merge_same_trip_intake_rows
should_autofill_field = _intake.should_autofill_field
