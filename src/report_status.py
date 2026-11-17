"""Persist only explicit RTGS status edits; financial fields are never changed."""

def persist_status_edits(store, rows, edited, user, snapshot, metadata):
    changed={row['request_number']:edited.iloc[index]['RTGS Status']=='RTGS Done'
             for index,row in enumerate(rows)
             if edited.iloc[index]['RTGS Status'] in ('Pending','RTGS Done')
             and (edited.iloc[index]['RTGS Status']=='RTGS Done')!=bool(row.get('rtgs_done'))}
    for done in (True,False):
        numbers=[number for number,value in changed.items() if value==done]
        if numbers:store.mark_rtgs_done(numbers,done=done,edited_by=user)
    trips,balances,upi=snapshot
    billtee=metadata[1]
    for row in rows:
        number=row['request_number']
        if number not in changed:continue
        done=changed[number]
        row['rtgs_done']=done
        prefix,_,raw=number.partition(':')
        queues={'BALANCE':balances,'UPI':upi,'BILLTEE':billtee}
        if prefix in queues:
            if raw in queues[prefix]:queues[prefix][raw]['rtgs_done']=done
        else:
            for trip in trips:
                if trip.get('request_number')==number:trip['rtgs_done']=done
    return len(changed)
