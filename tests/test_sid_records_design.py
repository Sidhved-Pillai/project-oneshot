from src import shyam_records_design


def test_sid_records_styles_are_scoped_to_sid(monkeypatch):
    styles = []
    monkeypatch.setattr(shyam_records_design.st, 'markdown', lambda value, **kwargs: styles.append(value))

    shyam_records_design.styles('sid')

    assert len(styles) == 1
    assert '.st-key-sid_records_table' in styles[0]
    assert '.st-key-sid_records_filters' in styles[0]
    assert '.st-key-shyam_records_table' not in styles[0]
