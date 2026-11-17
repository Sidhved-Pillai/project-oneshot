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
    assert not bool(edited.iloc[0]['Select'])
    pd.testing.assert_frame_equal(edited.drop(columns=['RTGS Status','Select']),frame.drop(columns=['RTGS Status','Select']))
    pd.testing.assert_frame_equal(apply_grid_event(frame,event,'v2',['RTGS Status']),frame)


def test_financial_edits_are_rejected_even_if_client_claims_editable():
    frame=pd.DataFrame([{'Account Number':'001234','Amount':100.0,'Select':False}])
    event={'revision':'v1','patches':[{'row':0,'column':'Account Number','value':'000789'},
        {'row':0,'column':'Amount','value':-1},{'row':0,'column':'Select','value':True}]}
    edited=apply_grid_event(frame,event,'v1',list(frame.columns))
    assert edited.iloc[0]['Account Number']=='001234'
    assert edited.iloc[0]['Amount']==100
    assert not bool(edited.iloc[0]['Select'])


def test_inflight_status_click_survives_revision_and_row_reordering():
    frame=pd.DataFrame([{'Record':'B','RTGS Status':'RTGS Done'},
                        {'Record':'A','RTGS Status':'Pending'}])
    event={'revision':'old','patches':[{'record':'B','column':'RTGS Status','value':'Pending'},
                                     {'record':'missing','column':'RTGS Status','value':'Pending'}]}
    result=apply_grid_event(frame,event,'new',['RTGS Status'])
    assert result['RTGS Status'].tolist()==['Pending','Pending']


def test_client_retains_second_click_until_server_acknowledges_it():
    import subprocess
    from pathlib import Path
    source=Path('src/rtgs_grid_component/index.html').read_text()
    function=source[source.index('function reconcileRows('):source.index('let menuAnchor=null;')]
    script='const patches=new Map();\n'+function+'''
patches.set('A|RTGS Status',{record:'A',column:'RTGS Status',value:'Pending'});
patches.set('B|RTGS Status',{record:'B',column:'RTGS Status',value:'Pending'});
let rows=reconcileRows([{Record:'B','RTGS Status':'RTGS Done'},{Record:'A','RTGS Status':'Pending'}]);
if(rows[0]['RTGS Status']!=='Pending'||patches.size!==1)throw Error('Lost second click');
rows=reconcileRows([{Record:'A','RTGS Status':'Pending'},{Record:'B','RTGS Status':'Pending'}]);
if(patches.size!==0)throw Error('Acknowledged clicks retained');
'''
    subprocess.run(['node','-e',script],check=True,capture_output=True)
