from .column_mapping import CONSOLIDATED_ALIASES, resolve_columns

def validate_consolidated(columns):
    found = resolve_columns(columns, CONSOLIDATED_ALIASES)
    required = ["Remark", "Beneficiary Name"]
    return [name for name in required if name not in found]

