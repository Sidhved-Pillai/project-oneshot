"""Resolve payment grouping and bank-profile owner using the same person rules."""
import json
import re
from difflib import SequenceMatcher
from .vehicle_placer import canonical_vehicle_placer


def person_login(value):
    text = ' '.join(re.findall(r'[a-z]+', str(value or '').casefold()))
    aliases = {'nit':'Nitish', 'nitish':'Nitish', 'nitish jha':'Nitish',
               'nitish kumar jha':'Nitish', 'gopal':'Nitish', 'ajit':'Ajit',
               'ajit thakur':'Ajit', 'manish':'Manish', 'manish jha':'Manish'}
    if text in aliases:
        return aliases[text]
    canonical = canonical_vehicle_placer(value)
    if canonical.casefold() in aliases:
        return aliases[canonical.casefold()]
    matches = {owner for alias, owner in aliases.items() if len(text) >= 4
               and SequenceMatcher(None, text, alias).ratio() >= .84}
    return next(iter(matches)) if len(matches) == 1 else None


def reimbursement_owner(trip):
    raw = trip.get('dtr_data') or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = {}
    creator = str(trip.get('created_by') or '').strip()
    if creator.casefold() == 'gopal':
        return 'Nitish'
    return person_login(raw.get('Veh Placed by')) or person_login(creator) or creator
