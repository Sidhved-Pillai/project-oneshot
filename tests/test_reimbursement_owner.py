import json
import pytest
from src.reimbursement_owner import reimbursement_owner
from src.pending_payments import payment_groups
from src.records_store_v27 import RequestStore
from tests.test_pending_payments import trip
from tests.test_billtee_payments import seed_profile


@pytest.mark.parametrize('kind', ['billtee','upi'])
def test_name_variants_and_assistant_merge_without_losing_trips(kind):
    rows = [{'request_number':str(i), 'created_by':creator, 'upi':100,
             'dtr_data':{'Veh Placed by':name, 'Billtee':100}}
            for i,(creator,name) in enumerate([
                ('Nitish','Nitish Jha'), ('Sid','Nit'), ('Gopal','Gopal'),
                ('Imported','Nitesh Jha'), ('Ajit','Ajit Thakur'), ('Manish','Manish Jha')])]
    groups = payment_groups(rows, kind, {}, {'Nitish':{'BNF_NAME':'Example','BENE_ACC_NO':'001','BENE_IFSC':'TEST0000001'}})
    assert {group[0]['name'] for group in groups} == {'Ajit','Manish','Nitish'}
    nitish = next(group for group in groups if group[0]['name'] == 'Nitish')
    assert len(nitish) == 4
    assert sum(item['amount'] for group in groups for item in group) == 600
    assert all(item['profile']['BENE_ACC_NO'] == '001' for item in nitish)


@pytest.mark.parametrize('kind', ['billtee','upi'])
def test_gopal_submissions_use_nitish_profile_and_preserve_original_trip(tmp_path, kind):
    store = RequestStore(f'sqlite:///{tmp_path / (kind + ".db")}')
    seed_profile(store)
    number = trip(store, created_by='Gopal', dtr_data={'Veh Placed by':'Gopal', 'Billtee':100})
    before = store.get(number)
    assert store.send_pending_payments({number:before['updated_at']},kind,'Nikhat') == 1
    queue = store.list_billtee_payments() if kind == 'billtee' else store.list_upi_payments()
    beneficiary = json.loads(queue[number]['rtgs_data'])
    assert beneficiary['BENE_ACC_NO'] == '009876'
    assert beneficiary['BNF_NAME'] == 'Test Branch Head'
    assert store.get(number) == before


def test_unknown_person_is_not_assigned_someone_elses_bank_details():
    assert reimbursement_owner({'created_by':'Unknown', 'dtr_data':{'Veh Placed by':'Unrelated'}}) == 'Unknown'
