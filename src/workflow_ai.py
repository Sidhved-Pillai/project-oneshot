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

Create one DTR row per RTGS trip row. Carry the trip date, vehicle, route, vehicle type, company, beneficiary, transporter and stated payment into the matching DTR fields when explicitly present. In this workflow the RTGS trip amount belongs in RTGS ADVANCE. Preserve missing late-arriving LR, invoice, diesel, UPI, revenue and freight values as blank for Shyam to complete. Do not merge trips.
"""
    return extract_intake(api_key, "DTR", context, files or [], model=model)
