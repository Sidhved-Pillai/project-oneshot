"""Persist only explicit RTGS status edits; financial fields are never changed."""

def persist_status_edits(store, rows, edited, user, snapshot, metadata):
    def status(row):
        return 'Mark for Later' if row.get('rtgs_later') else 'RTGS Done' if row.get('rtgs_done') else 'Pending'
    changed={row['request_number']:edited.iloc[index]['RTGS Status']
             for index,row in enumerate(rows)
             if edited.iloc[index]['RTGS Status'] in ('Pending','RTGS Done','Mark for Later')
             and edited.iloc[index]['RTGS Status'] != status(row)}
    for value in ('Pending','RTGS Done','Mark for Later'):
        numbers=[number for number,choice in changed.items() if choice==value]
        if numbers:
            kwargs = {'later': True} if value == 'Mark for Later' else {}
            store.mark_rtgs_done(numbers,done=value=='RTGS Done',edited_by=user,**kwargs)
    trips,balances,upi=snapshot
    billtee=metadata[1]
    for row in rows:
        number=row['request_number']
        if number not in changed:continue
        done=changed[number]=='RTGS Done'
        later=changed[number]=='Mark for Later'
        row['rtgs_done']=done
        row['rtgs_later']=later
        prefix,_,raw=number.partition(':')
        queues={'BALANCE':balances,'UPI':upi,'BILLTEE':billtee}
        if prefix in queues:
            if raw in queues[prefix]:queues[prefix][raw].update(rtgs_done=done, rtgs_later=later)
        else:
            for trip in trips:
                if trip.get('request_number')==number:trip.update(rtgs_done=done, rtgs_later=later)
    return len(changed)
