"""Searchable expense inputs learned from coherent saved beneficiary snapshots."""
import json
import re
import streamlit as st
from .vehicle_normalization import canonical_vehicle_number


def beneficiary_key(value):
    return re.sub(r'[^A-Z0-9]', '', str(value or '').strip().upper())


def expense_suggestions(rows):
    profiles, names, vehicles = {}, {}, set()
    for row in sorted(rows, key=lambda r: (str(r.get('updated_at') or r.get('created_at') or ''), int(r.get('id') or 0))):
        if row.get('is_archived') or row.get('status') not in {'Verified','Submitted'}:
            continue
        vehicle = canonical_vehicle_number(row.get('vehicle_number'))
        if vehicle:
            vehicles.add(vehicle)
        name = str(row.get('beneficiary_name') or '').strip()
        key = beneficiary_key(name)
        if not key:
            continue
        names[key] = name
        raw = row.get('rtgs_data') or {}
        raw = json.loads(raw) if isinstance(raw, str) else raw
        account, ifsc = str(raw.get('BENE_ACC_NO') or '').strip(), str(raw.get('BENE_IFSC') or '').strip()
        if account or ifsc:
            profiles[key] = {'account': account, 'ifsc': ifsc}
    return profiles, sorted(names.values(), key=str.casefold), sorted(vehicles)


def apply_expense_beneficiary(prefix, profiles):
    profile = profiles.get(beneficiary_key(st.session_state.get(f'{prefix}_beneficiary')), {})
    st.session_state[f'{prefix}_bank_account'] = profile.get('account', '')
    st.session_state[f'{prefix}_ifsc'] = profile.get('ifsc', '')


def expense_identity_inputs(prefix, beneficiary_column, vehicle_column, rows):
    profiles, names, vehicles = expense_suggestions(rows)
    name = str(st.session_state.get(f'{prefix}_beneficiary') or '').strip()
    vehicle = str(st.session_state.get(f'{prefix}_vehicle') or '').strip()
    names = ['', *sorted(set(names + ([name] if name else [])), key=str.casefold)]
    vehicles = ['', *sorted(set(vehicles + ([vehicle] if vehicle else [])))]
    beneficiary = beneficiary_column.selectbox('Beneficiary name', names,
        key=f'{prefix}_beneficiary', accept_new_options=True, placeholder='Type or select a beneficiary',
        on_change=apply_expense_beneficiary, args=(prefix, profiles))
    selected_vehicle = vehicle_column.selectbox('Vehicle name / number', vehicles,
        key=f'{prefix}_vehicle', accept_new_options=True, placeholder='Type or select a vehicle')
    return beneficiary, selected_vehicle
