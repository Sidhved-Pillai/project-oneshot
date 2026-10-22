import ast
import datetime as dt
import json
import re
from pathlib import Path

import pytest

from src.invoice_numbers_v3 import user_invoice_duplicates
from src.invoice_numbers import user_lr_duplicates


@pytest.mark.parametrize('user', ['Manish','Vijay','Ashok','Nitish','Ajit','Sid'])
def test_invoice_exception_is_only_for_manish_and_lr_checks_remain(user):
    row = {'created_by':user,'status':'Verified','invoice_number':'GST/GST/123/26-27',
           'dtr_data':{'LR No.':'LR-100'}}
    assert bool(user_invoice_duplicates([row],user,'GST/GST/123/26-27')) == (user != 'Manish')
    assert user_lr_duplicates([row],user,'LR-100') == [row]
    assert user_lr_duplicates([row],user,'LR-101') == []


def test_duplicate_review_uses_manish_lr_not_invoice():
    tree=ast.parse(Path('app.py').read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='duplicate_records')
    namespace={'re':re,'clean_text':lambda v:str(v or '').strip(),
               'as_date':lambda v:v,'number':lambda v:float(v or 0),
               'unpack':lambda v:json.loads(v) if isinstance(v,str) else (v or {})}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'app.py','exec'),namespace)
    base={'created_by':'Manish','report_scope':'Both','trip_date':dt.date(2026,10,22),
          'vehicle_number':'MH1234','invoice_number':'REPEATED'}
    rows=[dict(base,id=1,dtr_data={'LR No.':'LR-100'}),
          dict(base,id=2,dtr_data={'LR No.':'LR-101'}),
          dict(base,id=3,invoice_number='OTHER',dtr_data={'LR No.':'LR-100'}),
          dict(base,id=4,dtr_data={})]
    assert namespace['duplicate_records'](rows)==[rows[2]]
