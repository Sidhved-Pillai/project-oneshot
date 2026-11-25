"""Approved trip companies and explicitly added names."""
import json

from .company_brands import saint_gobain_brand


COMPANIES = (
    'Bisleri International Private Limited',
    'G.K.FOUNDERS PVT. LTD.',
    'Hindustan Coca-Cola Beverages Pvt Ltd',
    'Saint Gobain - Gyproc',
    'Saint Gobain - Weber',
    'Shree Sadgurukrupa Transport -Sonalco',
    'Ubiquity Transtech Pvt. Ltd.',
    'Vimal Logistic',
    'V.K.Patel & Co. (Ply Age)',
    'Empty Vehicle',
    'MYK (Adarsh Logistics)',
)
ADD_NEW = 'Add New + (for new companies)'
NEEDS_REVIEW = 'Saint Gobain - Needs Review'
NEEDS_COMPANY_REVIEW = 'Company Name - Needs Review'
COMPANY_REVIEW_USERS = frozenset({'Sid', 'Vinod', 'Nikhil', 'Nikhat', 'Ajit', 'Shyam'})


def is_saint_gobain_name(value):
    compact = ''.join(c for c in str(value or '').casefold() if c.isalpha())
    return compact == 'sg' or 'saintgob' in compact or saint_gobain_brand(value) is not None


def _data(row):
    raw = row.get('dtr_data') or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    return raw if isinstance(raw, dict) else {}


def company_choices(rows, saved_names=()):
    """Legacy typos do not become choices; explicitly added companies do."""
    custom = ({str(row.get('company_name') or '').strip() for row in rows
               if _data(row).get('_custom_company_name')}
              | {str(name or '').strip() for name in saved_names})
    return ['', *COMPANIES, *sorted(custom - set(COMPANIES) - {''}, key=str.casefold), ADD_NEW]


def is_unresolved_saint_gobain(row):
    if row.get('report_scope') == 'Expense':
        return False
    names = [row.get('company_name'), _data(row).get('Compnay Name')]
    saint = any(is_saint_gobain_name(name) for name in names)
    brands = {brand for name in names if (brand := saint_gobain_brand(name))}
    return saint and len(brands) != 1


def is_unapproved_company(row):
    name = str(row.get('company_name') or '').strip()
    return (bool(name) and name not in COMPANIES and not _data(row).get('_custom_company_name')
            and row.get('report_scope') != 'Expense')
