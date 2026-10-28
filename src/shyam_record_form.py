"""Shyam's side-by-side evidence and record form."""
import datetime as dt
import math

import streamlit as st
import streamlit.components.v1 as components

from .invoice_viewer import invoice_viewer_html


def record_form(display, evidence, request_number, locked, branches):
    image_col, form_col = st.columns([1, 1.15], gap='large')
    replacement = None
    with image_col:
        st.markdown('#### Invoice evidence')
        if evidence.get('source_image'):
            mime = evidence.get('source_mime_type') or ''
            if mime.startswith('image/'):
                components.html(invoice_viewer_html(evidence['source_image'], mime), height=520)
            else:
                st.download_button('Open invoice evidence', evidence['source_image'],
                                   evidence.get('source_filename') or 'invoice.pdf', mime or 'application/pdf')
        else:
            st.caption('No invoice evidence attached.')
        replacement = st.file_uploader('Replace or attach invoice', type=['png','jpg','jpeg','webp','pdf'],
                                       key=f'shyam_evidence_{request_number}')
    values = dict(display)
    with form_col, st.form(f'shyam_record_form_{request_number}'):
        sections = [
            ('1. Basic information', ['Date','Type','Branch','Company','From','To','LR No.','Invoice No.']),
            ('2. Vehicle information', ['Vehicle','Vehicle Capacity','Own / Outside','Vehicle Placed By']),
            ('3. Beneficiary details', ['Transporter Name','Beneficiary','Account Number','IFSC']),
            ('4. Payment details', ['Revenue','Transporter Freight','UPI','Diesel','Cash','RTGS','Billtee',
                                    'Diesel Qty','Diesel Rate','Add Pumps','Card Name','Toll Expense',
                                    'Repairs & Maintenance','Reason','Profit / Loss']),
        ]
        for heading, fields in sections + [('Expense details', [key for key in display if key not in
                {field for _, fields in sections for field in fields} and key != 'Remarks'])]:
            fields = [field for field in fields if field in display]
            if not fields:
                continue
            st.markdown(f'#### {heading}')
            columns = st.columns(2)
            for index, field in enumerate(fields):
                column = columns[index % 2]
                value = display[field]
                key = f'shyam_edit_{request_number}_{field}'
                options = branches if field == 'Branch' else ['', 'Own', 'Outside'] if field == 'Own / Outside' else None
                if options is not None:
                    options = list(dict.fromkeys([*options, str(value or '')]))
                    values[field] = column.selectbox(field, options, index=options.index(str(value or '')),
                                                     key=key, disabled=field in locked)
                elif isinstance(value, (dt.date, dt.datetime)) or field == 'Date' or 'Period ' in field:
                    values[field] = column.date_input(field, value=value, format='DD/MM/YYYY', key=key,
                                                     disabled=field in locked)
                elif isinstance(value, (int, float)):
                    amount = float(value)
                    values[field] = column.number_input(field, value=amount if math.isfinite(amount) else 0.0,
                                                         key=key, disabled=field in locked)
                else:
                    values[field] = column.text_input(field, value=str(value or ''), key=key,
                                                       disabled=field in locked)
        values['Remarks'] = st.text_area('Remarks', value=str(display.get('Remarks') or ''),
                                        key=f'shyam_edit_{request_number}_remarks')
        submitted = st.form_submit_button('Save changes', type='primary')
    return values, replacement, submitted
