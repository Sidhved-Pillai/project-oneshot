"""Auditable year-only correction of active operational records."""
import datetime as dt
import json


def year_correction(row):
    old = row['trip_date']
    if old.year >= 2026:
        return None
    new = old.replace(year=2026)  # deliberately rejects invalid leap-day dates
    dtr = json.loads(row.get('dtr_data') or '{}') if isinstance(row.get('dtr_data'),str) else dict(row.get('dtr_data') or {})
    rtgs = json.loads(row.get('rtgs_data') or '{}') if isinstance(row.get('rtgs_data'),str) else dict(row.get('rtgs_data') or {})
    dtr['Date'] = new.isoformat()
    def remark(value):
        text = str(value or '')
        for fmt in ('%Y-%m-%d','%d/%m/%Y','%d %m %Y','%d-%m-%Y'):
            text = text.replace(old.strftime(fmt),new.strftime(fmt))
        return text
    for data in (dtr, rtgs):
        for key in ('Remark','REMARK'):
            if key in data:
                data[key] = remark(data[key])
    def periods(value):
        if isinstance(value,dict):
            return {k:periods(v) for k,v in value.items()}
        if isinstance(value,list):
            corrected = [periods(v) for v in value]
            if len(corrected) == 2 and all(isinstance(v,str) for v in corrected):
                try:
                    start, end = [dt.date.fromisoformat(v) for v in corrected]
                except ValueError:
                    pass
                else:
                    if end < start:
                        raise ValueError('Year correction would reverse an expense period')
            return corrected
        if isinstance(value,str):
            try:
                date = dt.date.fromisoformat(value)
            except ValueError:
                return value
            return date.replace(year=2026).isoformat() if date.year < 2026 else value
        return value
    if 'periods' in dtr:
        dtr['periods'] = periods(dtr['periods'])
    return {'trip_date':new,'dtr_data':dtr,'rtgs_data':rtgs,'notes':remark(row.get('notes'))}
