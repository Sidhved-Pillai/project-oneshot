import ast
import json
from pathlib import Path

import pandas as pd


def test_missing_vijay_payments_are_visible_without_inventing_amounts():
    tree = ast.parse(Path('app.py').read_text())
    names = {'clean_text', 'number', 'unpack', 'vijay_trips_missing_rtgs'}
    scope = dict(pd=pd, json=json, canonical_vehicle_placer=lambda v:v,
                 is_own_vehicle=lambda v:str(v or '').lower().startswith('own'))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=selected,type_ignores=[]),'app.py','exec'),scope)
    rows = [dict(created_by='Vijay', ownership_type='Outside', rtgs_advance=0),
            dict(created_by='Vijay', ownership_type='Outside', rtgs_advance=100),
            dict(created_by='Vijay', ownership_type='Own', rtgs_advance=0),
            dict(created_by='Nitish', ownership_type='Outside', rtgs_advance=0),
            dict(created_by='Sid', ownership_type='Outside', rtgs_advance=0,
                 dtr_data={'Veh Placed by':'Vijay'})]
    assert scope['vijay_trips_missing_rtgs'](rows) == [rows[0], rows[4]]
    assert rows[0]['rtgs_advance'] == 0
