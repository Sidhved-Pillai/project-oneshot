"""Refresh company review access rules on warm Streamlit deployments."""
import importlib
from . import company_catalog

_module = importlib.reload(company_catalog)
COMPANIES = _module.COMPANIES
ADD_NEW = _module.ADD_NEW
NEEDS_COMPANY_REVIEW = _module.NEEDS_COMPANY_REVIEW
COMPANY_REVIEW_USERS = _module.COMPANY_REVIEW_USERS
company_choices = _module.company_choices
is_saint_gobain_name = _module.is_saint_gobain_name
is_unresolved_saint_gobain = _module.is_unresolved_saint_gobain
is_unapproved_company = _module.is_unapproved_company
