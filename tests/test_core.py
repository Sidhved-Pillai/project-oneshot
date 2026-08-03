from io import BytesIO
import datetime as dt
import pandas as pd
from openpyxl import Workbook, load_workbook
import pytest
from src.excel_reader import detect_header_row
from src.column_mapping import resolve_columns, DTR_ALIASES, CONSOLIDATED_ALIASES
from src.remark_classifier import classify_remark
from src.remark_parser import normalize_vehicle, last_four, normalize_vehicle_type, parse_remark
from src.vehicle_matcher import find_vehicle, resolve_vehicle, choose_vehicle_type
from src.master_builder import build_vehicle_master, build_company_master, build_beneficiary_master
from src.dtr_generator import generate_dtr, final_review_rows, DTR_COLUMNS, FINANCIAL_COLUMNS
from src.excel_exporter import export_dtr
from src.gemini_parser import parse_with_gemini
from src.historical_suggester import HistoricalSuggester
from src.entry_finance import financial_values
from src.request_store import RequestStore, rows_to_dtr
from src.rtgs_report import RTGS_COLUMNS, export_rtgs, rows_to_rtgs


def vehicle_master():
    return pd.DataFrame([
        {"Vehicle No.": "MH14JL9818", "Last 4 Digits": "9818", "Vehicle Type": "10MT", "Ownership Type": "Outside Vehicle", "Transporter Name": "Vehicle Carrier", "Vehicle Status": "Active"},
        {"Vehicle No.": "MH12AB9818", "Last 4 Digits": "9818", "Vehicle Type": "12MT", "Ownership Type": "Own Vehicle", "Transporter Name": "", "Vehicle Status": "Active"},
        {"Vehicle No.": "MH04AA8172", "Last 4 Digits": "8172", "Vehicle Type": "21MT", "Ownership Type": "Outside Vehicle", "Transporter Name": "Master Carrier", "Vehicle Status": "Active"},
        {"Vehicle No.": "MH01AB0272", "Last 4 Digits": "0272", "Vehicle Type": "20MT", "Ownership Type": "Outside Vehicle", "Transporter Name": "Zero Carrier", "Vehicle Status": "Active"},
        {"Vehicle No.": "MH99XX0001", "Last 4 Digits": "0001", "Vehicle Type": "10MT", "Ownership Type": "Outside Vehicle", "Transporter Name": "", "Vehicle Status": "Inactive"},
    ])


def beneficiary_master():
    return pd.DataFrame([{"Beneficiary Account No.": "001234", "Beneficiary Name": "Demo", "Transporter Name": "Account Carrier"}])


def source(remarks):
    return pd.DataFrame({"Remark": remarks, "Beneficiary Name": ["Demo"] * len(remarks),
                         "Beneficiary Account No": ["001234"] * len(remarks)})


def test_header_detection_with_blank_rows():
    ws = Workbook().active; ws.append([]); ws.append(["report title"]); ws.append(["Remark", "Beneficiary Name"])
    assert detect_header_row(ws, ["Remark", "Beneficiary Name"]) == 3


def test_column_mappings():
    assert resolve_columns(["Compnay Name", "Own/Outside Veh."], DTR_ALIASES)["Own/Outside Vehicle"] == "Own/Outside Veh."
    assert resolve_columns(["Remarks", "Beneficiary Name"], CONSOLIDATED_ALIASES)["Remark"] == "Remarks"


def test_vehicle_normalization_and_last_four():
    assert normalize_vehicle("mh 14-jl 9818") == "MH14JL9818"
    assert last_four("MH14JL9818") == "9818"


def test_duplicate_suffix_and_inactive_filtering():
    assert len(find_vehicle("9818", vehicle_master())) == 2
    assert find_vehicle("0001", vehicle_master()) == []


def test_unique_suffix_resolves_to_full_vehicle_and_master_fields():
    number, match, choices = resolve_vehicle(["0272"], vehicle_master())
    assert number == "MH01AB0272" and match["Vehicle Type"] == "20MT" and choices == ["MH01AB0272"]


def test_full_registration_normalizes_and_matches_directly():
    number, match, choices = resolve_vehicle(["mh 04-aa 8172"], vehicle_master())
    assert number == "MH04AA8172" and match["Ownership Type"] == "Outside Vehicle"


def test_unmatched_suffix_remains_unresolved_and_leading_zero_survives():
    number, match, choices = resolve_vehicle(["0099"], vehicle_master())
    assert number == "0099" and not match and choices == []


def test_multiple_identifiers_preserved_without_automatic_choice():
    parsed = parse_remark("6789 7890 Shriwal to Bhiwandi 12MT 29 30 07 2026 TA")
    assert parsed["vehicle_identifiers"] == ["6789", "7890"] and parsed["vehicle_identifier"] == ""


def test_vehicle_conflicts_are_not_silently_resolved():
    a = pd.DataFrame({"Vehicle No.":["MH14JL9818"],"Vehicle Type":["10MT"],"Own/Outside Veh.":["Outside Vehicle"],"Transporter Name":["A"]})
    b = a.copy(); b.loc[0,"Vehicle Type"] = "12MT"
    master, conflicts = build_vehicle_master([a,b])
    assert master.iloc[0]["Vehicle Type"] == "" and len(conflicts) == 1


@pytest.mark.parametrize("remark,master,expected,conflict", [
    ("25MT", "", "25MT", False), ("", "21MT", "21MT", False),
    ("25MT", "25MT", "25MT", False), ("25MT", "21MT", "25MT", True),
])
def test_vehicle_type_precedence(remark, master, expected, conflict):
    assert choose_vehicle_type(remark, master) == (expected, conflict)


def test_company_branch_deduplication():
    df = pd.DataFrame({"Compnay Name":["SG","SG"],"Branch":["Pune","Pune"]})
    assert len(build_company_master([df])) == 1


def test_beneficiary_accounts_preserved_as_strings():
    df = pd.DataFrame({"Beneficiary Account No":["001234","001234"],"Beneficiary Name":["Demo","Demo"]})
    master, _ = build_beneficiary_master(df)
    assert master.iloc[0]["Beneficiary Account No."] == "001234" and len(master) == 1


def test_salary_is_confirmed_non_trip_and_number_not_vehicle():
    result = classify_remark("Driver Salary for June 2026 8595 Laxman", ["8595"])
    assert (result.classification, result.reason) == ("Confirmed Non-trip", "Driver Salary")
    assert parse_remark("Driver Salary for June 2026 8595 Laxman")["vehicle_identifiers"] == []


@pytest.mark.parametrize("remark,expected", [
    ("7348 Wagholi to Kamshet 07 08 2026 TA", "Confirmed Trip"),
    ("9416 Jhagadia to Indore 09MT 31 07 2026 TA", "Confirmed Trip"),
    ("6765 Talegaon to Pimpri 30 07 2026 TA", "Confirmed Trip"),
    ("6305 Bhiwandi to Pune Balance Payment 2LR TP", "Potential Trip"),
    ("9818 29 07 2026 to 31 07 2026 3Trp TA", "Potential Trip"),
    ("4094 25 07 2026 to 28 07 2026 2Trp TA", "Potential Trip"),
    ("Balance Payment as per ledger TP", "Potential Trip"),
    ("Amount paid as Transporter Payment Thru UPI", "Potential Trip"),
    ("Vasai Local Transporter Payment", "Potential Trip"),
])
def test_classification_regressions(remark, expected):
    assert classify_remark(remark).classification == expected


@pytest.mark.parametrize("remark,vehicle,origin,destination,kind,date", [
    ("7348 Wagholi to Kamshet 07 08 2026 TA", "7348", "Wagholi", "Kamshet", "", "07-08-2026"),
    ("9416 Jhagadia to Indore 09MT 31 07 2026 TA", "9416", "Jhagadia", "Indore", "9MT", "31-07-2026"),
    ("6765 Talegaon to Pimpri 30 07 2026 TA", "6765", "Talegaon", "Pimpri", "", "30-07-2026"),
    ("6305 Bhiwandi to Pune Balance Payment 2LR TP", "6305", "Bhiwandi", "Pune", "", None),
    ("3946 Talegaon to Hinjewadi 5k card diesal 25MT 26 07 2026 TA", "3946", "Talegaon", "Hinjewadi", "25MT", "26-07-2026"),
    ("0272 Wagholi to Kamshet 20MT 27 07 2026 TA", "0272", "Wagholi", "Kamshet", "20MT", "27-07-2026"),
])
def test_actual_style_route_parsing(remark, vehicle, origin, destination, kind, date):
    parsed = parse_remark(remark)
    assert parsed["vehicle_identifiers"] == [vehicle]
    assert parsed["from_location"] == origin and parsed["to_location"] == destination
    assert parsed["vehicle_type"] == kind
    assert (parsed["date"].strftime("%d-%m-%Y") if parsed["date"] is not None else None) == date


def test_unusual_adjacent_days_best_effort():
    parsed = parse_remark("6789 7890 Shriwal to Bhiwandi 12MT 29 30 07 2026 TA")
    assert parsed["from_location"] == "Shriwal" and parsed["to_location"] == "Bhiwandi"
    assert parsed["vehicle_type"] == "12MT" and parsed["date"].strftime("%d-%m-%Y") == "30-07-2026"


@pytest.mark.parametrize("value", ["30 07 2026", "30/07/2026", "30.07.26"])
def test_all_supported_remark_date_formats(value):
    assert parse_remark(f"9818 Pune to Mumbai 10MT {value} TA")["date"].strftime("%d-%m-%Y") == "30-07-2026"


def test_pipe_format_extracts_company_and_fields():
    parsed = parse_remark("9818 | SG | Talegaon to Bhiwandi | 10MT | 30 07 2026 | INV 0012345 | TA")
    assert parsed["vehicle_identifiers"] == ["9818"]
    assert parsed["company_name"] == "SG" and parsed["from_location"] == "Talegaon" and parsed["to_location"] == "Bhiwandi"
    assert parsed["vehicle_type"] == "10MT" and parsed["date"].strftime("%d-%m-%Y") == "30-07-2026"
    assert parsed["invoice_number"] == "0012345"


@pytest.mark.parametrize("remark,date", [
    ("9818 29 07 2026 to 31 07 2026 3Trp TA", "31-07-2026"),
    ("4094 25 07 2026 to 28 07 2026 2Trp TA", "28-07-2026"),
])
def test_date_range_uses_end_date_one_row(remark, date):
    confirmed, potential, _ = generate_dtr(source([remark]), vehicle_master(), beneficiary_master())
    assert confirmed.empty and len(potential) == 1
    assert potential.iloc[0]["Date"].strftime("%d-%m-%Y") == date
    assert potential.iloc[0]["From"] == "" and potential.iloc[0]["To"] == ""


@pytest.mark.parametrize("marker", ["INV", "Invoice", "Invoice No", "Bill No"])
def test_invoice_markers_and_leading_zero(marker):
    assert parse_remark(f"1234 Pune to Mumbai 10MT {marker} 00127")["invoice_number"] == "00127"


def test_generator_account_priority_and_remark_type_conflict():
    confirmed, potential, non_trip = generate_dtr(source(["8172 Jhagadia to Indore 25MT 31 07 2026 TA"]), vehicle_master(), beneficiary_master())
    row = confirmed.iloc[0]
    assert row["Vehicle No."] == "MH04AA8172" and row["Vehicle Type"] == "25MT" and bool(row["_needs_review"]) and bool(row["_type_conflict"])
    assert row["Transporter Name"] == "Account Carrier"


def test_beneficiary_always_comes_from_uploaded_report_without_master():
    empty_beneficiaries = pd.DataFrame(columns=["Beneficiary Account No.", "Beneficiary Name", "Transporter Name"])
    confirmed, _, _ = generate_dtr(source(["7348 Wagholi to Kamshet 10MT 07 08 2026 TA"]), vehicle_master(), empty_beneficiaries)
    assert confirmed.iloc[0]["Benificiary Name"] == "Demo" and confirmed.iloc[0]["Transporter Name"] == ""


def test_payment_date_never_fills_missing_remark_date():
    frame = source(["7348 Wagholi to Kamshet 10MT TA"])
    frame["Pymt_Date"] = ["30-07-2026"]
    confirmed, _, _ = generate_dtr(frame, vehicle_master(), beneficiary_master())
    assert pd.isna(confirmed.iloc[0]["Date"])


def test_historical_suggestions_are_conservative_and_explicit_company_wins():
    suggester = HistoricalSuggester({
        "routes": {"jhagadia|indore": {"company": "SG", "branch": "Vadodara"}},
        "route_companies": {"talegaon|bhiwandi|sg": {"branch": "Pune"}},
    })
    assert suggester.suggest("Jhagadia", "Indore") == ("SG", "Vadodara")
    assert suggester.suggest("Talegaon", "Bhiwandi", "SG") == ("SG", "Pune")
    assert suggester.suggest("New", "Route") == ("", "")


def test_every_input_is_accounted_for_and_potential_not_auto_included():
    remarks = ["7348 Wagholi to Kamshet 07 08 2026 TA", "Balance Payment as per ledger TP", "Driver Salary for June 2026 8595 Laxman"]
    confirmed, potential, non_trip = generate_dtr(source(remarks), vehicle_master(), beneficiary_master())
    assert len(confirmed) + len(potential) + len(non_trip) == len(remarks)
    assert not potential.iloc[0]["Include in DTR"]
    assert len(final_review_rows(confirmed, potential)) == 1
    potential.loc[:, "Include in DTR"] = True
    assert len(final_review_rows(confirmed, potential)) == 2


def test_exact_columns_blank_financials_and_export_date_format_width():
    frame = pd.DataFrame([{**{c:"" for c in DTR_COLUMNS}, "Sr No.":1, "Date":pd.Timestamp("2026-07-30"),
                           "Vehicle No.":"MH01AB0272", "Invoice No.":"00127", "Revenue":"999"}])
    data = export_dtr(frame); ws = load_workbook(BytesIO(data))["DTR"]
    assert [c.value for c in ws[1]] == DTR_COLUMNS and ws.freeze_panes == "A2" and ws.auto_filter.ref
    assert isinstance(ws["D2"].value, (dt.datetime, dt.date)) and ws["D2"].number_format == "dd-mm-yyyy"
    assert 13 <= ws.column_dimensions["D"].width <= 15
    assert ws["E2"].number_format == "@" and ws["I2"].number_format == "@" and ws["I2"].value == "00127"
    assert all(ws.cell(2, DTR_COLUMNS.index(c)+1).value is None for c in FINANCIAL_COLUMNS)
    assert ws.max_column == 22


def test_missing_required_column():
    with pytest.raises(ValueError, match="Missing required"):
        generate_dtr(pd.DataFrame({"Remark":["trip"]}), vehicle_master(), beneficiary_master())


def test_gemini_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert parse_with_gemini("ambiguous") is None


def test_financial_mapping_and_persistent_request_roundtrip(tmp_path):
    finance = financial_values("Trip Advance", "UPI", 1250, 12.5)
    assert finance["upi"] == 1250 and finance["total_advance"] == 1250
    store = RequestStore(f"sqlite:///{tmp_path / 'requests.db'}")
    number = store.create({
        "trip_date": dt.date(2026, 8, 3), "vehicle_number": "MH14JL9818",
        "invoice_number": "INV-7", "company_name": "Demo Co", "expense_type": "Trip Advance",
        "amount": 1250, "payment_mode": "UPI", **finance, "status": "Submitted",
        "source_filename": "proof.jpg", "source_mime_type": "image/jpeg", "source_image": b"proof",
    })
    assert number.startswith("REQ-202608-")
    reopened = RequestStore(f"sqlite:///{tmp_path / 'requests.db'}")
    rows = reopened.list(dt.date(2026, 8, 1), dt.date(2026, 8, 31))
    assert len(rows) == 1 and rows[0]["source_image"] == b"proof"
    dtr = rows_to_dtr(rows)
    assert dtr.iloc[0]["UPI"] == 1250 and dtr.iloc[0]["Invoice No."] == "INV-7"


def test_archive_hides_without_deleting(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'archive.db'}")
    store.create({"trip_date": dt.date(2026, 7, 1), "vehicle_number": "MH01AA0001"})
    assert store.archive_before(dt.date(2026, 8, 1)) == 1
    assert store.list() == []
    assert len(store.list(include_archived=True)) == 1


def test_rtgs_roundtrip_filter_and_exact_export_columns(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'rtgs.db'}")
    store.create({
        "report_scope": "RTGS", "trip_date": dt.date(2026, 8, 4), "vehicle_number": "",
        "beneficiary_name": "Demo Beneficiary", "amount": 4500, "status": "Verified",
        "rtgs_data": {"Pymt_Mode": "NEFT", "Beneficiary Account No": "001234",
                      "Bene_IFSC_Code": "DEMO0001234", "Remark": "Office expense",
                      "Pymt_Date": dt.date(2026, 8, 4)},
    })
    assert store.list(report_kind="DTR") == []
    rows = store.list(report_kind="RTGS")
    frame = rows_to_rtgs(rows)
    assert list(frame.columns) == RTGS_COLUMNS
    assert frame.iloc[0]["Beneficiary Name"] == "Demo Beneficiary"
    assert frame.iloc[0]["Beneficiary Account No"] == "001234"
    ws = load_workbook(BytesIO(export_rtgs(frame)))["Sheet0"]
    assert [cell.value for cell in ws[1]] == RTGS_COLUMNS
    assert ws["F2"].value == "001234" and ws["F2"].number_format == "@"


def test_both_scope_appears_in_both_reports(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'both.db'}")
    store.create({"report_scope": "Both", "trip_date": dt.date(2026, 8, 4),
                  "vehicle_number": "MH01AA0001", "rtgs_data": {"Remark": "Trip advance"}})
    assert len(store.list(report_kind="DTR")) == 1
    assert len(store.list(report_kind="RTGS")) == 1
