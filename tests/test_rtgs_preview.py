import pandas as pd
from streamlit.testing.v1 import AppTest
from src.rtgs_preview import preview_table
from tests.test_report_studio import report_source, apply
from tests.test_report_filters import run


def test_preview_is_read_only_and_escapes_invoice_content():
    frame=pd.DataFrame([{'Sr. No.':7,'Branch':'Wada','Transporter Name':'<script>bad</script>',
        'Vehicle No.':'MH1','Invoice No.':'001234','Beneficiary':'A & B','Amount':1250.5}])
    result=preview_table(frame)
    assert '<script>' not in result and '&lt;script&gt;' in result
    assert '001234' in result and '1,250.50' in result and 'A &amp; B' in result
    assert '<input' not in result


def test_create_opens_preview_and_cancel_does_not_confirm(tmp_path):
    source=report_source(tmp_path/'preview.db').replace('complete_rtgs_download=lambda *args:None',
        "def complete_rtgs_download(*args):\n    st.session_state['confirmed']=True")
    app=AppTest.from_string(source).run()
    apply(app,'RTGS')
    app.button(key='create_rtgs_preview').click();run(app)
    assert not app.exception
    assert app.get('dialog')
    assert any(b.label=='Confirm' for b in app.get('download_button'))
    assert 'confirmed' not in app.session_state
    app.button(key='rtgs_preview_cancel_button').click();run(app)
    assert not app.exception and not app.get('dialog')
    assert 'confirmed' not in app.session_state


def test_pending_rows_are_grouped_last_without_changing_export_identity(tmp_path):
    from src.request_store import RequestStore
    from tests.test_pending_payments import trip
    import datetime as dt
    path=tmp_path/'order.db'
    app=AppTest.from_string(report_source(path)).run()
    store=RequestStore('sqlite:///'+str(path))
    trip(store,trip_date=dt.date(2026,11,11),invoice_number='SENT',rtgs_advance=50)
    rows=store.dashboard_snapshot()[0]
    sent=next(r for r in rows if r['invoice_number']=='SENT')
    store.mark_rtgs_done([sent['request_number']],edited_by='Sid')
    apply(app,'RTGS')
    frame=app.session_state['_rtgs_badge_table']['frame']
    assert frame['RTGS Status'].tolist()==['RTGS Done','Pending']
    assert frame['Invoice No.'].tolist()==['SENT','TEST-INV']
    assert frame['Select'].tolist()==[False,True]
    assert app.session_state['rtgs_export_frame'].iloc[0]['AMOUNT']==1000


def test_nikhat_no_longer_has_an_extra_save_button(tmp_path):
    app=AppTest.from_string(report_source(tmp_path/'nikhat.db').replace("current_user='Sid'","current_user='Nikhat'")).run()
    apply(app,'RTGS')
    assert not any('Save RTGS changes' in b.label for b in app.button)


def test_nikhat_inline_correction_saves_without_extra_button(tmp_path):
    from tests.test_report_filters import run
    from src.request_store import RequestStore
    path=tmp_path/'autosave.db'
    source=report_source(path).replace("current_user='Sid'", "current_user='Nikhat'")
    pos=source.rfind('render_generate_reports()')
    source=source[:pos]+'''original_editor=report_editor
def report_editor(*args, **kwargs):
    result=original_editor(*args, **kwargs)
    if args[2]=='report_rtgs_grid' and st.session_state.pop('test_edit_financial',False):
        result.iloc[0,result.columns.get_loc('Amount')]=1200
        result.iloc[0,result.columns.get_loc('Beneficiary')]='Corrected beneficiary'
    return result
render_generate_reports()
'''
    app=AppTest.from_string(source).run();apply(app,'RTGS')
    app.session_state['test_edit_financial']=True
    run(app)
    assert not app.exception
    row=RequestStore('sqlite:///'+str(path)).dashboard_snapshot()[0][0]
    assert row['rtgs_advance']==1200 and row['beneficiary_name']=='Corrected beneficiary'
