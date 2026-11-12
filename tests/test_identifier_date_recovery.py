import datetime as dt
from src.batched_records_v9 import filter_identifiers
from src.record_lookup import outside_date_identifier_matches
from src.entry_date_confirmation import entry_date_requires_confirmation


def row(**extra):
    return {'request_number':'REQ-202611-003761','report_scope':'Both','status':'Verified',
            'trip_date':dt.date(2026,11,27),'created_by':'Ajit','branch':'Wada',
            'vehicle_number':'MH14LX7414','ownership_type':'Outside',
            'invoice_number':'TON270284354',
            'dtr_data':{'LR No.':'TON270284354','Veh Placed by':'Ajit Thakur'},**extra}


def filters(**extra):
    return {'start':dt.date(2026,10,1),'end':dt.date(2026,11,12),
            'lr_number':'ton 270-284354','invoice_number':'','vehicle':'All','placer':'All','ownership':'Both',**extra}


def test_duplicate_identifier_can_be_found_despite_date_and_punctuation():
    target=row()
    assert filter_identifiers([target],filters())==[target]
    assert outside_date_identifier_matches([target],filters())==[target]
    assert filter_identifiers([target],filters(lr_number='',invoice_number='TON-270284354'))==[target]
    assert outside_date_identifier_matches([target],filters(lr_number='',invoice_number='TON-270284354'))==[target]


def test_outside_date_lookup_preserves_scoping_other_filters_and_only_targets_identifiers():
    for extra in ({'lr_number':''},{'vehicle':'MH00NONE'},{'placer':'Nitish Jha'},
                  {'ownership':'Own'},{'lr_number':'missing'},{'invoice_number':'missing'}):
        assert outside_date_identifier_matches([row()],filters(**extra))==[]
    assert outside_date_identifier_matches([],filters())==[]  # caller's access scope is never broadened
    assert outside_date_identifier_matches([row(is_archived=True)],filters())==[]
    assert outside_date_identifier_matches([row(status='Cancelled')],filters())==[]
    assert outside_date_identifier_matches([row(trip_date=dt.date(2026,10,27))],filters())==[]
    assert outside_date_identifier_matches([row()],filters(vehicle='MH14LX7414',placer='Ajit Thakur'))


def test_same_month_future_day_requires_confirmation_not_just_other_months():
    today=dt.date(2026,11,12)
    assert entry_date_requires_confirmation(dt.date(2026,11,27),today)
    assert entry_date_requires_confirmation(dt.date(2026,10,27),today)
    assert entry_date_requires_confirmation(dt.date(2026,12,1),today)
    assert not entry_date_requires_confirmation(today,today)
    assert not entry_date_requires_confirmation(dt.date(2026,11,1),today)
    assert not entry_date_requires_confirmation(None,today)
