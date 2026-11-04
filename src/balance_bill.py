"""Read-only transporter settlement bills captured when balances are queued."""
import datetime as dt
import html
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .invoice_display import dtr_invoice_text
from .number_format import format_inr


COLUMNS = ['Sr. No.', 'Date', 'Vehicle No.', 'MT', 'Plant', 'LR No.', 'Invoice No.',
           'Customer Name', 'Location', 'Freight Amt.', 'Cash Adv.', 'RTGS Adv.',
           'UPI Adv.', 'Diesel Qty', 'Diesel Adv.', 'Net Adv.', 'Balance Amt.', 'LR Status']
MONEY = ['Freight Amt.', 'Cash Adv.', 'RTGS Adv.', 'UPI Adv.', 'Diesel Qty', 'Diesel Adv.', 'Net Adv.', 'Balance Amt.']
WIDTHS = [5,12,17,8,14,16,22,32,18,14,13,13,13,11,13,14,14,14]


def data(value):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or '{}')
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def money(value):
    try:
        number = Decimal(str(value or 0))
        return number.quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if number.is_finite() else Decimal(0)
    except (ValueError, ArithmeticError):
        return Decimal(0)


def bill_trip(row, queued_amount):
    raw = data(row.get('dtr_data'))
    billtee = money(raw.get('Billtee'))
    cash, rtgs, upi, diesel = (money(row.get(field)) for field in ('cash_advance','rtgs_advance','upi','diesel_advance'))
    return {'request_number':row['request_number'], 'Date':str(row.get('trip_date') or '')[:10],
            'Vehicle No.':row.get('vehicle_number') or '', 'MT':row.get('vehicle_type') or '',
            'Plant':row.get('from_location') or '', 'LR No.':raw.get('LR No.',''),
            'Invoice No.':dtr_invoice_text(raw.get('Invoice No.') or row.get('invoice_number')),
            'Customer Name':raw.get('Customer Name',''), 'Location':row.get('to_location') or '',
            'Freight Amt.':str(money(row.get('transporter_freight'))),
            'Cash Adv.':str(cash), 'RTGS Adv.':str(rtgs), 'UPI Adv.':str(upi),
            'Diesel Qty':str(money(raw.get('Diesel Qty') or row.get('diesel_quantity'))),
            'Diesel Adv.':str(diesel), 'Net Adv.':str(cash+rtgs+upi+diesel),
            # The queued payment is authoritative. Billtee is shown once below.
            'Balance Amt.':str(money(queued_amount)+billtee), 'billtee':str(billtee),
            'queued_amount':str(money(queued_amount)), 'LR Status':raw.get('LR Status','')}


def bill_group_key(row):
    raw, profile = data(row.get('dtr_data')), data(row.get('rtgs_data'))
    name = row.get('transporter_name') or raw.get('Transporter Name') or row.get('beneficiary_name') or 'Transporter'
    identity = re.sub(r'[^a-z0-9]', '', name.casefold()).replace('vikash','vikas')
    return (identity, str(profile.get('BNF_NAME') or row.get('beneficiary_name') or '').strip(),
            str(profile.get('BENE_ACC_NO') or '').strip(), str(profile.get('BENE_IFSC') or '').strip())


def make_bill(rows, user):
    first = rows[0][0]
    raw = data(first.get('dtr_data'))
    profile = data(first.get('rtgs_data'))
    return {'transporter':first.get('transporter_name') or raw.get('Transporter Name') or first.get('beneficiary_name') or 'Transporter',
            'profile':{key:str(profile.get(key) or (first.get('beneficiary_name') if key == 'BNF_NAME' else '') or '')
                       for key in ('BNF_NAME','BENE_ACC_NO','BENE_IFSC','Bank Name')},
            'requested_by':user, 'rows':[bill_trip(row, value) for row,value in sorted(rows,key=lambda pair:(str(pair[0].get('trip_date')),pair[0]['request_number']))]}


def totals(bill):
    rows = bill['rows']
    result = {field:sum((money(row.get(field)) for row in rows),Decimal(0)) for field in MONEY}
    result['billtee'] = sum((money(row.get('billtee')) for row in rows),Decimal(0))
    result['grand_total'] = sum((money(row.get('queued_amount')) for row in rows),Decimal(0))
    result['adjustment'] = result['Freight Amt.'] - result['Net Adv.'] - result['Balance Amt.']
    return result


def words(number):
    units = ['Zero','One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen']
    tens = ['', '', 'Twenty','Thirty','Forty','Fifty','Sixty','Seventy','Eighty','Ninety']
    def integer(n):
        if n < 20: return units[n]
        if n < 100: return tens[n//10] + (' ' + units[n%10] if n%10 else '')
        for scale,label in ((10000000,'Crore'),(100000,'Lakh'),(1000,'Thousand'),(100,'Hundred')):
            if n >= scale: return integer(n//scale)+' '+label+(' '+integer(n%scale) if n%scale else '')
    value = money(number)
    whole = int(abs(value)); paise = int((abs(value)-whole)*100)
    return ('Minus ' if value < 0 else '') + integer(whole) + ' Rupees' + (' and '+integer(paise)+' Paise' if paise else '') + ' Only'


def date_text(value):
    try: return dt.date.fromisoformat(str(value)[:10]).strftime('%d/%m/%Y')
    except ValueError: return str(value or '')


def payment_status(bill):
    statuses = bill.get('payment_status', {})
    paid = sum(statuses.get(row['request_number']) is True for row in bill['rows'])
    return 'Paid / RTGS Done' if paid == len(bill['rows']) else 'Sent to RTGS — payment pending' if not paid else f'Partly paid — {paid} of {len(bill["rows"])} trips marked RTGS Done'


def render_bill_html(bill):
    esc = lambda value: html.escape(str(value or ''))
    table_amount = lambda value: format_inr(money(value),2).replace('₹','')
    total = totals(bill)
    cells = []
    for index,row in enumerate(bill['rows'],1):
        values = {**row,'Sr. No.':index,'Date':date_text(row['Date'])}
        cells.append('<tr>'+''.join('<td>'+esc(table_amount(values.get(col)) if col in MONEY and col != 'Diesel Qty' else values.get(col,''))+'</td>' for col in COLUMNS)+'</tr>')
    sums = '<tr class="total">'+''.join('<td>'+ (esc(str(total[col]) if col == 'Diesel Qty' else table_amount(total[col])) if col in MONEY else 'Total' if col == 'Sr. No.' else '')+'</td>' for col in COLUMNS)+'</tr>'
    profile = bill['profile']
    adjustment = f'<p>Saved-record reconciliation difference: {esc(format_inr(total["adjustment"]))}. The grand total matches the amounts submitted to RTGS.</p>' if total['adjustment'] else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    body{{font:11px Arial;color:#111;margin:14px}}h2{{text-align:center;margin:8px 0 30px}}table{{border-collapse:collapse;width:100%;table-layout:fixed}}td,th{{border:1px solid #222;padding:5px 3px;overflow-wrap:anywhere}}td:nth-child(2),td:nth-child(n+10):nth-child(-n+17){{font-size:9px;white-space:nowrap}}td:nth-child(n+10):nth-child(-n+17){{text-align:right}}th{{font-style:italic;background:#f5f7fa}}.total{{font-weight:bold}}.head,.footer{{display:flex;justify-content:space-between;gap:20px;margin:10px 0}}.bank{{border:1px solid #222;padding:12px;min-width:45%}}.signature{{text-align:right;margin:45px 60px 10px}}button{{padding:9px 18px;cursor:pointer}}@page{{size:A4 landscape;margin:9mm}}@media print{{button{{display:none}}body{{margin:0;font-size:8px}}td:nth-child(2),td:nth-child(n+10):nth-child(-n+17){{font-size:7px}}thead{{display:table-header-group}}tr{{break-inside:avoid}}}}
    </style></head><body><button onclick="window.print()">Print / Save PDF</button>
    <h2>{esc(bill['transporter'])}</h2><div class="head"><div>To,<br><b>Ubiquity Transtech Pvt Ltd.</b></div><div><b>Bill No.: {esc(bill['bill_number'])}</b><br>Date: {esc(date_text(bill['created_at']))}<br>{esc(payment_status(bill))}</div></div>
    <table><colgroup>{''.join(f'<col style="width:{width/sum(WIDTHS)*100:.2f}%">' for width in WIDTHS)}</colgroup><thead><tr>{''.join('<th>'+esc(col)+'</th>' for col in COLUMNS)}</tr></thead><tbody>{''.join(cells)}{sums}</tbody></table>
    <div class="footer"><div class="bank"><b>Bank Detail :- NEFT/RTGS</b><br>Name: {esc(profile.get('BNF_NAME'))}<br>A/c No.: {esc(profile.get('BENE_ACC_NO'))}<br>IFSC: {esc(profile.get('BENE_IFSC'))}<br>Bank Name: {esc(profile.get('Bank Name'))}</div><div>Transporter Adv. for Billtee paid: <b>{esc(format_inr(total['billtee']))}</b><h3>Grand Total: {esc(format_inr(total['grand_total']))}</h3></div></div>
    {adjustment}<p><b>Rupees in Words: {esc(words(total['grand_total']))}</b></p><p>RTGS submission statement. Payment status reflects the app's RTGS Done marking.</p><div class="signature">Authorised Signature</div></body></html>'''


def export_bill(bill):
    wb = Workbook(); ws = wb.active; ws.title = 'Transporter Bill'
    def safe(value):
        return "'"+value if isinstance(value,str) and value.startswith(('=','+','-','@')) else value
    def merged(row,start,end,text,bold=False):
        ws.merge_cells(start_row=row,start_column=start,end_row=row,end_column=end)
        cell=ws.cell(row,start,safe(text)); cell.font=Font(name='Arial',size=11,bold=bold); cell.alignment=Alignment(vertical='center',wrap_text=True)
    merged(1,1,18,bill['transporter'],True);ws['A1'].alignment=Alignment(horizontal='center',vertical='center');ws['A1'].font=Font(name='Arial',size=17,bold=True);ws.row_dimensions[1].height=45
    merged(3,1,11,'To,\nUbiquity Transtech Pvt Ltd.',True);merged(3,12,18,'Bill No.: '+bill['bill_number'],True);ws.row_dimensions[3].height=32
    merged(4,12,18,'Date: '+date_text(bill['created_at']))
    merged(5,1,18,payment_status(bill),True)
    for col,name in enumerate(COLUMNS,1):
        cell=ws.cell(7,col,name);cell.font=Font(name='Arial',bold=True,italic=True,size=10,color='C00000' if name in MONEY else '000000');cell.fill=PatternFill('solid',fgColor='F2F5FA');cell.alignment=Alignment(wrap_text=True,horizontal='center')
    ws.row_dimensions[7].height=32
    for index,row in enumerate(bill['rows'],1):
        values={**row,'Sr. No.':index,'Date':date_text(row['Date'])}
        for col,name in enumerate(COLUMNS,1):
            val=float(money(row.get(name))) if name in MONEY else safe(values.get(name,''))
            cell=ws.cell(7+index,col,val);cell.alignment=Alignment(wrap_text=True,vertical='center');cell.font=Font(name='Arial',size=10)
            if name in MONEY:cell.number_format='#,##0.00'
        ws.row_dimensions[7+index].height=29
    total=totals(bill);last=8+len(bill['rows'])
    ws.cell(last,1,'Total')
    for col,name in enumerate(COLUMNS,1):
        if name in MONEY: ws.cell(last,col,float(total[name])).number_format='#,##0.00'
        ws.cell(last,col).font=Font(name='Arial',bold=True,size=10)
    merged(last+2,1,9,'Bank Detail :- NEFT/RTGS',True)
    for offset,(label,key) in enumerate([('Name','BNF_NAME'),('A/c No.','BENE_ACC_NO'),('IFSC','BENE_IFSC'),('Bank Name','Bank Name')],3):
        merged(last+offset,1,9,label+': '+bill['profile'].get(key,''))
    merged(last+2,10,16,'Transporter Adv. for Billtee paid:',True)
    ws.cell(last+2,17,float(total['billtee'])).number_format='#,##0.00'
    merged(last+7,1,13,'Rupees in Words: '+words(total['grand_total']),True)
    merged(last+7,14,16,'Grand Total:',True);ws.cell(last+7,17,float(total['grand_total'])).number_format='#,##0.00'
    merged(last+9,1,18,'RTGS submission statement. Payment status reflects the app RTGS Done marking.')
    if total['adjustment']:merged(last+10,1,18,'Saved-record reconciliation difference: '+format_inr(total['adjustment'])+'; grand total matches submitted RTGS amounts.')
    merged(last+12,13,18,'Authorised Signature')
    thin=Side(style='thin',color='333333')
    for row in ws.iter_rows(min_row=7,max_row=last,max_col=18):
        for cell in row:cell.border=Border(left=thin,right=thin,top=thin,bottom=thin)
    for col,width in enumerate(WIDTHS,1):ws.column_dimensions[get_column_letter(col)].width=width
    ws.sheet_view.showGridLines=False;ws.freeze_panes='A8';ws.print_title_rows='1:7';ws.print_area=f'A1:R{last+13}'
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0;ws.sheet_properties.pageSetUpPr.fitToPage=True
    output=BytesIO();wb.save(output);return output.getvalue()
