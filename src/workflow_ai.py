"""Workflow AI helpers kept in a deployment-stable module.

Streamlit Cloud can retain already-imported modules across a Git pull. This
module name was introduced with the workflow release so its functions cannot
be confused with an older cached ``ai_intake`` module.
"""

import json

from .ai_intake import extract_intake


def revise_intake(api_key, mode, current_records, instruction, files=None, model=None):
    context = f"""
CURRENT REVIEWED {mode} TABLE (authoritative starting point):
{json.dumps(current_records, default=str)}

OPERATOR CHANGE REQUEST:
{instruction or 'No AI change instruction was supplied. Preserve the table.'}

Return the complete revised table, not only changed rows. Preserve every existing value unless the operator explicitly changes it or stronger attached evidence clearly conflicts. Never drop a row silently; flag uncertainty in Review Notes.
"""
    return extract_intake(api_key, mode, context, files or [], model=model)


def convert_rtgs_to_dtr(api_key, rtgs_records, instruction, files=None, model=None):
    context = f"""
Create Shyam's DTR draft from Nikhat's finalized RTGS rows below.
FINALIZED RTGS TABLE:
{json.dumps(rtgs_records, default=str)}

SHYAM'S INSTRUCTIONS:
{instruction or '(none supplied)'}

Create one DTR row per underlying trip, expanding a grouped RTGS remark such as "7872 02 08 2026 to 04 08 2026 3Trp TA" when the original WhatsApp text supplies the individual dates/routes. Carry the trip date, last four vehicle digits, route, vehicle type, company, beneficiary and transporter into each matching DTR row. In this workflow each trip's Rs amount belongs in RTGS ADVANCE. Carry Transporter Freight from the RTGS workflow field or original trip text into the matching DTR row; divide a grouped total only when the source explicitly gives equal per-trip freight. Preserve missing late-arriving LR, invoice, diesel, UPI and revenue values as blank for Shyam to complete. Never merge DTR trips.
"""
    return extract_intake(api_key, "DTR", context, files or [], model=model)
