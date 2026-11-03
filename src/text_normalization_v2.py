"""Refresh company business-name normalization after deployment."""
import importlib
from . import text_normalization
_normalization = importlib.reload(text_normalization)
canonical_company = _normalization.canonical_company
canonical_location = _normalization.canonical_location
canonical_ownership = _normalization.canonical_ownership
canonical_vehicle_capacity = _normalization.canonical_vehicle_capacity
plain_remark = _normalization.plain_remark
