"""Refresh duplicate review permissions on hot deployment."""
import importlib
from . import dashboard_duplicate_review
review_duplicates = importlib.reload(dashboard_duplicate_review).review_duplicates
