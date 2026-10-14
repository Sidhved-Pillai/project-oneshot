import datetime as dt

import pytest
from streamlit.testing.v1 import AppTest

from tests.test_ashok_dtr_sync import translator


def test_record_calendar_starts_in_2026():
    app = AppTest.from_string('''
import datetime as dt
from src.batched_records_v3 import render_filters
render_filters([], 'Sid', dt.date(2026,10,14))
''').run()
    assert not app.exception
    for widget in app.date_input:
        assert widget.proto.min == '2026/01/01'


def test_manual_dtr_date_cannot_save_before_operational_start():
    with pytest.raises(ValueError):
        translator()({'created_by':'Ajit','dtr_data':{},'rtgs_data':{}}, {'Date':'2016-10-14'})
    with pytest.raises(ValueError):
        translator()({'created_by':'Ajit','dtr_data':{},'rtgs_data':{}}, {'Date':'2025-12-31'})
