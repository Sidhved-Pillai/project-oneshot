import ast
import datetime as dt
import hashlib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from src.dtr_dates import parse_dtr_date


def functions(extract):
    tree = ast.parse(Path('app.py').read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in
                {'evidence', 'autofill', 'retry_evidence', 'file_values', 'capture_photo'}]
    state = {}
    st = SimpleNamespace(session_state=state, spinner=lambda *a: nullcontext(),
                         error=lambda *a: None, warning=lambda *a: None, success=lambda *a: None)
    scope = dict(st=st, hashlib=hashlib, dt=dt, current_user='Nitish', secret=lambda name: 'test',
                 parse_dtr_date=parse_dtr_date,
                 allowed_entry_branches=['Pune'], normalization_rows=[], PRIORITY_FIELDS=[],
                 scan_context=lambda instruction,*args:instruction,
                 recover_entry_fields=lambda result,*args:result,
                 extract_intake=extract, should_autofill_field=lambda *a: True,
                 normalized_invoice_numbers=lambda v: v, clean_text=lambda v: str(v or ''))
    exec(compile(ast.Module(body=selected, type_ignores=[]), 'app.py', 'exec'), scope)
    return scope, state


def test_confirmed_camera_photo_is_used_for_autofill_and_saved_evidence():
    calls = []
    row = SimpleNamespace(model_dump=lambda: {'vehicle_number':'MH12AB1234'}, invoice_numbers=[], lr_invoice_number='')
    def extract(*args):
        calls.append(args)
        return SimpleNamespace(rows=[row]), None
    scope, state = functions(extract)
    photo = SimpleNamespace(name='camera.jpg', type='image/jpeg', getvalue=lambda: b'photo-bytes')
    files = scope['evidence']([photo], None)
    scope['autofill'](files, '', 'trip_0')
    assert state['trip_0_vehicle_number'] == 'MH12AB1234'
    assert calls[0][3] == files
    assert scope['file_values'](files)['source_image'] == b'photo-bytes'
    scope['autofill'](files, '', 'trip_0')
    assert len(calls) == 1


def test_failed_photo_can_be_retried_without_repeated_background_requests():
    calls = []
    def extract(*args):
        calls.append(args)
        raise RuntimeError('temporary extraction failure')
    scope, state = functions(extract)
    files = [{'filename':'camera.jpg', 'mime_type':'image/jpeg', 'data':b'photo'}]
    scope['autofill'](files, '', 'trip_0')
    assert 'trip_0_evidence_hash' not in state
    scope['autofill'](files, '', 'trip_0')
    assert len(calls) == 1
    scope['retry_evidence']('trip_0')
    scope['autofill'](files, '', 'trip_0')
    assert len(calls) == 2
