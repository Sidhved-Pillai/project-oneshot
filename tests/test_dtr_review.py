from io import BytesIO
import datetime as dt

import pandas as pd
import pytest

from src.dtr_review import app_review_frame, compare_dtr, identity, read_review_sheet


def trip(invoice="123", owner="Ashok"):
    return {"Date": "04/10/2026", "Vehicle No.": "MH04 HD4001", "Invoice No.": invoice,
            "Veh Placed by": owner, "From": "Pune", "To": "Mumbai"}


def test_dates_and_numeric_identifiers_are_normalized():
    assert identity(trip())["date"] == dt.date(2026, 10, 4)
    assert identity({**trip(), "Date": "2026-10-04 00:00:00"})["date"] == dt.date(2026, 10, 4)
    assert identity(trip(123.0))["invoice"] == frozenset({"123"})
    assert identity({**trip(), "Created By": "Shyam"})["owner"] == "Ashok"


def test_review_matches_one_to_one_and_groups_missing_without_writes():
    uploaded = pd.DataFrame([trip(), trip("456"), trip(), {"Date": "TOTAL"}])
    app = pd.DataFrame([{**trip(123.0), "App Record": "REQ-1"}])
    before = uploaded.copy(deep=True)
    ticks = []
    result, counts = compare_dtr(uploaded, app, progress=lambda *args: ticks.append(args))
    assert result["Review Status"].tolist() == ["Found in App", "Missing from App", "Repeated upload row", "Invalid / non-trip row"]
    assert counts == {"Ashok": 1}
    assert result.iloc[0]["Matched App Record"] == "REQ-1"
    assert ticks[-1] == (4, 4, 1)
    pd.testing.assert_frame_equal(uploaded, before)


def test_ambiguous_matches_and_unknown_owner_are_not_misreported():
    app = pd.DataFrame([trip(), trip()])
    result, counts = compare_dtr(pd.DataFrame([trip()]), app)
    assert result.iloc[0]["Review Status"].startswith("Needs review")
    assert counts == {}
    _, counts = compare_dtr(pd.DataFrame([trip(owner="")]), pd.DataFrame())
    assert counts == {"Unassigned": 1}
    _, counts = compare_dtr(pd.DataFrame([trip(owner="")]), pd.DataFrame(), "Nitish")
    assert counts == {"Nitish": 1}


def test_route_fallback_and_multiple_invoices():
    app = pd.DataFrame([{**trip("123 / 124"), "App Record": "REQ-1"}])
    result, _ = compare_dtr(pd.DataFrame([trip("124")]), app)
    assert result.iloc[0]["Review Status"] == "Found in App"
    result, _ = compare_dtr(pd.DataFrame([trip("")]), app)
    assert result.iloc[0]["Review Status"] == "Found in App"
    result, _ = compare_dtr(pd.DataFrame([{**trip(""), "To": "Delhi"}]), app)
    assert result.iloc[0]["Review Status"] == "Missing from App"


def test_app_frame_excludes_expenses_deleted_and_cancelled():
    base = {"request_number": "REQ-1", "trip_date": dt.date(2026, 10, 4),
            "vehicle_number": "MH04HD4001", "created_by": "Ashok", "dtr_data": '{"Invoice No.":"123"}'}
    frame = app_review_frame([base, {**base, "report_scope": "Expense"},
                             {**base, "is_archived": True}, {**base, "status": "Cancelled"}])
    assert len(frame) == 1
    assert frame.iloc[0]["Invoice No."] == "123"


def test_excel_title_rows_and_legacy_headings():
    output = BytesIO()
    pd.DataFrame([{"Date": dt.date(2026, 10, 4), "Vehicle Number": "MH04HD4001"}]).to_excel(
        output, index=False, startrow=3, sheet_name="DTR")
    output.seek(0)
    frame = read_review_sheet(output, "DTR")
    assert len(frame) == 1
    assert identity(frame.iloc[0].to_dict())["date"] == dt.date(2026, 10, 4)
    bad = BytesIO()
    pd.DataFrame({"Other": [1]}).to_excel(bad, index=False)
    bad.seek(0)
    with pytest.raises(ValueError):
        read_review_sheet(bad, "Sheet1")


def test_review_ui_uses_read_only_spreadsheets(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    uploaded = BytesIO()
    pd.DataFrame([trip(), trip("456")]).to_excel(uploaded, index=False)
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: BytesIO(uploaded.getvalue()))
    app = AppTest.from_string('''
from src.dtr_review import render_dtr_review
render_dtr_review([{"request_number":"REQ-1", "trip_date":"2026-10-04",
    "vehicle_number":"MH04HD4001", "invoice_number":"123", "created_by":"Ashok"}])
''').run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert len(app.dataframe) == 3  # imported, app, and missing person rows
    assert "1 trips" in app.success[0].value


def test_shyam_login_code_is_1011_without_colliding_with_other_members():
    import ast
    import hashlib
    from pathlib import Path
    tree = ast.parse(Path("app.py").read_text())
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "MEMBER_CODE_HASHES" for target in node.targets))
    hashes = ast.literal_eval(assignment.value)
    digest = hashlib.pbkdf2_hmac("sha256", b"1011", bytes.fromhex("28d7f0e0dfb9b32fecf4f4656d309042"), 600_000).hex()
    assert hashes["Shyam"] == digest
    assert [user for user, value in hashes.items() if value == digest] == ["Shyam"]
