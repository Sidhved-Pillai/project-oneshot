import datetime as dt

from src.records_filter_url import encode_filters, decode_filters


def test_applied_records_filters_survive_url_round_trip():
    selected = {'start': dt.date(2026, 10, 31), 'end': dt.date(2026, 10, 31),
                'vehicle': 'MH04LE8412', 'record_type': 'Trip Records',
                'without_evidence': True, 'order': '↑'}
    assert decode_filters(encode_filters(selected)) == selected


def test_bad_or_unrelated_url_values_are_ignored():
    assert decode_filters('{bad') == {}
    assert decode_filters('{"vehicle":"MH04LE8412","admin":true}') == {'vehicle': 'MH04LE8412'}
