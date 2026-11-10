"""Conservative duplicate review for independently payable direct expenses."""
import hashlib
import json
import re
from collections.abc import Mapping
from .branch_names import canonical_branch


def expense_duplicate_signature(record):
    # A shared date/total is not evidence of a duplicate: offices, payees,
    # categories, payment details, notes and attachments must agree as well.
    volatile = {'id', 'request_number', 'created_at', 'updated_at', 'batch_id'}
    def canonical(value):
        if isinstance(value, Mapping):
            return {str(key):canonical(item) for key,item in value.items()}
        if isinstance(value, (list,tuple)):
            return [canonical(item) for item in value]
        if isinstance(value, bytes):
            return {'sha256':hashlib.sha256(value).hexdigest()}
        if isinstance(value, str):
            return re.sub(r'\s+', ' ', value).strip().casefold()
        return value
    details = {key:value for key,value in record.items() if key not in volatile}
    details['branch'] = canonical_branch(record.get('branch'))
    for field in ('dtr_data', 'rtgs_data'):
        if isinstance(details.get(field), str):
            try:
                details[field] = json.loads(details[field])
            except (TypeError, ValueError):
                pass
    return ('Direct expense', json.dumps(canonical(details), sort_keys=True, default=str))
