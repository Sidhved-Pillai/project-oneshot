"""Shared side-by-side evidence and record form for authorized record editors."""
import datetime as dt
import math

import streamlit as st
import streamlit.components.v1 as components

from .invoice_viewer import invoice_viewer_html
from .operational_dates import OPERATIONS_START
from .expense_review import expense_category_increase
from .pnl_report import REPORT_EXPENSE_COLUMNS
from .vehicle_placer import CANONICAL_VEHICLE_PLACERS, canonical_vehicle_placer
from .company_catalog import ADD_NEW, is_saint_gobain_name


@st.fragment
def invoice_preview(request_number, load_evidence):
    if st.button('View Invoice', icon=':material/description:', key=f'view_invoice_{request_number}'):
        with st.spinner('Loading invoice…'):
            evidence = load_evidence() or {}
        if evidence.get('source_image'):
            mime = evidence.get('source_mime_type') or ''
            if mime.startswith('image/'):
                components.html(invoice_viewer_html(evidence['source_image'], mime), height=520)
            else:
                st.download_button('Open invoice evidence', evidence['source_image'],
                                   evidence.get('source_filename') or 'invoice.pdf', mime or 'application/pdf')
        else:
            st.caption('No invoice evidence attached.')


def record_form(display, evidence, request_number, locked, branches, load_evidence=None, can_edit=True,
                companies=(), drivers=(), review_company=False):
    # The preview is its own fragment: loading a photo does not submit or rebuild
    # the form, so unsaved field edits remain in the browser.
    values = dict(display)
    empty_vehicle = str(display.get('Company') or '').strip() == 'Empty Vehicle'
    needs_company_choice = (not empty_vehicle and display.get('Type') != 'Direct expense'
                            and bool(companies) and display.get('Company') not in companies)
    if not empty_vehicle:
        invoice_preview(request_number, load_evidence or (lambda: evidence))
    with st.form(f'shyam_record_form_{request_number}'):
        sections = [('Empty vehicle trip', ['Date', 'Company', 'Vehicle', 'From', 'To'])] if empty_vehicle else [
            ('1. Basic information', ['Date','Type','Branch','Company','Customer Name','From','To','LR No.','Invoice No.']),
            ('2. Vehicle information', ['Driver Name','Vehicle','Vehicle Capacity','Own / Outside','Vehicle Placed By']),
            ('3. Beneficiary details', ['Transporter Name','Beneficiary','Account Number','IFSC']),
            ('4. Payment details', ['Revenue','Transporter Freight','UPI','Diesel','Cash','RTGS','Billtee',
                                    'Diesel Qty','Diesel Rate','Add Pumps','Card Name','Toll Expense',
                                    'Repairs & Maintenance','Reason','Profit / Loss']),
        ]
        for heading, fields in sections + ([] if empty_vehicle else [('Expense details', [key for key in display if key not in
                {field for _, fields in sections for field in fields} and key != 'Remarks'])]):
            fields = [field for field in fields if field in display]
            if not fields:
                continue
            st.markdown(f'#### {heading}')
            columns = st.columns(2)
            for index, field in enumerate(fields):
                column = columns[index % 2]
                value = display[field]
                key = f'shyam_edit_{request_number}_{field}'
                options = branches if field == 'Branch' else ['', 'Own', 'Outside'] if field == 'Own / Outside' else ['', *CANONICAL_VEHICLE_PLACERS] if field == 'Vehicle Placed By' else list(companies) if field == 'Company' and companies else None
                if options is not None:
                    selected = canonical_vehicle_placer(value) if field == 'Vehicle Placed By' else '' if field == 'Company' and (review_company or needs_company_choice) else str(value or '')
                    options = (['', 'Saint Gobain - Gyproc', 'Saint Gobain - Weber'] if field == 'Company' and review_company
                               else list(dict.fromkeys([*options, selected])) if field != 'Company' or not needs_company_choice
                               else list(companies))
                    values[field] = column.selectbox(field, options, index=options.index(selected),
                                                     key=key, disabled=field in locked)
                    if field == 'Company' and values[field] == ADD_NEW:
                        values[field] = column.text_input('New company name', key=f'{key}_new').strip()
                        values['_custom_company_name'] = bool(values[field])
                        values['_invalid_new_company'] = is_saint_gobain_name(values[field])
                elif field == 'Driver Name' and drivers:
                    options = list(dict.fromkeys(['', *drivers, str(value or '')]))
                    values[field] = column.selectbox(field, options, key=key,
                        accept_new_options=True, disabled=field in locked)
                elif isinstance(value, (dt.date, dt.datetime)) or field == 'Date' or 'Period ' in field:
                    values[field] = column.date_input(field, value=value, format='DD/MM/YYYY', key=key,
                                                     min_value=OPERATIONS_START, disabled=field in locked)
                elif isinstance(value, (int, float)):
                    amount = float(value)
                    values[field] = column.number_input(field, value=amount if math.isfinite(amount) else 0.0,
                                                         key=key, disabled=field in locked)
                else:
                    values[field] = column.text_input(field, value=str(value or ''), key=key,
                                                       disabled=field in locked)
        if not empty_vehicle:
            values['Remarks'] = st.text_area('Remarks', value=str(display.get('Remarks') or ''),
                                            key=f'shyam_edit_{request_number}_remarks', disabled=not can_edit)
        replacement = None if empty_vehicle else st.file_uploader('Replace or attach invoice',
            type=['png','jpg','jpeg','webp','pdf'], key=f'shyam_evidence_{request_number}', disabled=not can_edit)
        category_names = [name for name in REPORT_EXPENSE_COLUMNS if name in display]
        confirm_increase = True
        if category_names:
            before = {'categories': {name: display[name] for name in category_names}}
            after = {'categories': {name: values[name] for name in category_names}}
            if expense_category_increase(before, after):
                st.warning('An existing expense amount is still filled and you added another category. '
                           'If you are moving the expense, clear its old category to avoid counting it twice.')
                confirm_increase = st.checkbox('These are separate expenses; keep both category amounts',
                                              key=f'confirm_category_increase_{request_number}')
        if review_company:
            st.warning('Choose Gyproc or Weber after checking the trip evidence.')
        elif needs_company_choice:
            st.warning('Choose an approved company name before saving this trip.')
        if values.get('_invalid_new_company'):
            st.error('Select Saint Gobain - Gyproc or Saint Gobain - Weber from the list.')
        if empty_vehicle and not all(str(values.get(field) or '').strip() for field in ('Vehicle', 'From', 'To')):
            st.warning('Truck No., From, and To are required.')
        submitted = st.form_submit_button('Save changes', type='primary', disabled=not can_edit)
    valid_company = not (review_company or needs_company_choice) or bool(values.get('Company'))
    valid_empty_trip = not empty_vehicle or all(str(values.get(field) or '').strip()
                                                  for field in ('Vehicle', 'From', 'To'))
    return (values, replacement, submitted and confirm_increase and valid_company
            and valid_empty_trip and not values.get('_invalid_new_company', False))
