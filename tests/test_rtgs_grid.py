import pandas as pd
from src.rtgs_grid import apply_grid_event


def test_status_event_is_scoped_and_does_not_modify_financial_fields():
    frame=pd.DataFrame([{'Record':'REQ-A','RTGS Status':'RTGS Done','Select':False,'Amount':100,'Remarks':'Original'},
                        {'Record':'REQ-B','RTGS Status':'Pending','Select':False,'Amount':200,'Remarks':'Keep'}])
    event={'revision':'v1','patches':[{'row':0,'column':'RTGS Status','value':'Pending'},
        {'row':0,'column':'Amount','value':999},{'row':0,'column':'Record','value':'REQ-B'},
        {'row':1,'column':'RTGS Status','value':'bogus'},{'row':50,'column':'Select','value':True}]}
    edited=apply_grid_event(frame,event,'v1',['Select','RTGS Status'])
    assert edited.iloc[0]['RTGS Status']=='Pending'
    assert edited.iloc[1]['RTGS Status']=='Pending'
    pd.testing.assert_frame_equal(edited.drop(columns='RTGS Status'),frame.drop(columns='RTGS Status'))
    pd.testing.assert_frame_equal(apply_grid_event(frame,event,'v2',['RTGS Status']),frame)


def test_nikhat_can_edit_financial_details_without_losing_account_zeroes():
    frame=pd.DataFrame([{'Account Number':'001234','Amount':100.0,'Select':False}])
    event={'revision':'v1','patches':[{'row':0,'column':'Account Number','value':'000789'},
        {'row':0,'column':'Amount','value':-1},{'row':0,'column':'Select','value':True}]}
    edited=apply_grid_event(frame,event,'v1',list(frame.columns))
    assert edited.iloc[0]['Account Number']=='000789'
    assert edited.iloc[0]['Amount']==100
    assert bool(edited.iloc[0]['Select'])
