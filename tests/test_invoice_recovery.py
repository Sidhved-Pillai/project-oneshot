import pytest
from src.ai_intake import UnifiedIntakeResult, UnifiedIntakeRow
from src.invoice_recovery import recover_entry_fields, match_saved_vehicle, scan_context

FILES=[{'mime_type':'image/jpeg','data':b'photo','filename':'invoice.jpg'}]


def complete(**values):
    return UnifiedIntakeRow(**{'date':'2026-10-22','branch':'Pune','from_location':'Talegaon','to_location':'Mumbai',
        'lr_number':'LR100','invoice_number':'GST/GST/123/26-27','vehicle_number':'MH04LE8409',**values})


def test_missing_fields_get_one_high_detail_reread_without_overwriting_first_scan():
    result=UnifiedIntakeResult(rows=[complete(lr_number='',invoice_number='',to_location='')])
    calls=[]
    def extractor(*args,**kwargs):
        calls.append((args,kwargs))
        return UnifiedIntakeResult(rows=[complete(from_location='WRONG',to_location='Solapur')]),'test-model'
    recovered=recover_entry_fields(result,extractor,'test','context',FILES,None,['Pune'],[])
    assert len(calls)==1 and calls[0][1]['high_detail'] is True
    assert recovered.rows[0].lr_number=='LR100'
    assert recovered.rows[0].invoice_number=='GST/GST/123/26-27'
    assert recovered.rows[0].to_location=='Solapur'
    assert recovered.rows[0].from_location=='Talegaon'


def test_complete_scan_has_no_extra_request_and_fixed_login_branch_wins():
    result=UnifiedIntakeResult(rows=[complete(branch='Andheri',vehicle_number='MH04LE84O9')])
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected scan')
    recover_entry_fields(result,forbidden,'test','context',FILES,None,['Wada'],['MH04LE8409'])
    assert result.rows[0].branch=='Wada'
    assert result.rows[0].vehicle_number=='MH04LE8409'
    assert 'please verify' in result.rows[0].review_notes


@pytest.mark.parametrize('first_date', ['', '2016-10-22', 'unreadable'])
def test_unreliable_invoice_date_is_reread_from_header(first_date):
    result = UnifiedIntakeResult(rows=[complete(date=first_date)])
    calls = []
    def extractor(*args, **kwargs):
        calls.append((args, kwargs))
        return UnifiedIntakeResult(rows=[complete(date='2026-10-22')]), 'test'
    recover_entry_fields(result, extractor, 'test', 'context', FILES, None, ['Pune'], [])
    assert len(calls) == 1
    assert calls[0][1]['high_detail']
    assert 'Invoice Date' in calls[0][0][2]
    assert result.rows[0].date == '2026-10-22'


def test_failed_recovery_keeps_first_scan_and_never_invents_identifiers():
    result=UnifiedIntakeResult(rows=[complete(lr_number='',invoice_number='')])
    def failed(*args,**kwargs):raise RuntimeError('temporary API failure')
    recover_entry_fields(result,failed,'test','context',FILES,None,['Pune'],[])
    assert result.rows[0].lr_number==result.rows[0].invoice_number==''
    assert result.rows[0].from_location=='Talegaon'


@pytest.mark.parametrize('value,fleet,expected',[
    ('MH04LE84O9',['MH04LE8409'],'MH04LE8409'),
    ('8409',['MH04LE8409'],'MH04LE8409'),
    ('84O9',['MH04LE8409'],'MH04LE8409'),
    ('8409',['MH04LE8409','MH12AB8409'],'8409'),
    ('MH04LE8408',['MH04LE8409'],'MH04LE8408'),
    ('',['MH04LE8409'],''),
])
def test_vehicle_matching_needs_unique_visual_support(value,fleet,expected):
    assert match_saved_vehicle(value,fleet)==expected


def test_no_result_can_recover_once_and_voice_does_not_trigger_image_reread():
    calls=[]
    def extractor(*args,**kwargs):
        calls.append(1)
        return UnifiedIntakeResult(rows=[complete()]),None
    result=UnifiedIntakeResult()
    recover_entry_fields(result,extractor,'test','context',FILES,None,['Pune'],[])
    assert len(result.rows)==1 and len(calls)==1
    result=UnifiedIntakeResult(rows=[complete(lr_number='')])
    recover_entry_fields(result,extractor,'test','context',[{'mime_type':'audio/wav'}],None,['Pune'],[])
    assert len(calls)==1
    assert 'restricted to branch Wada' in scan_context('manual instruction','Manish',['Wada'])
