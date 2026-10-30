"""Bounded invoice rereading and conservative matching against the saved fleet."""
import json
import re
from .branch_names import canonical_branch
from .vehicle_normalization import canonical_vehicle_number
from .dtr_dates import parse_dtr_date

PRIORITY_FIELDS = ('branch','from_location','to_location','lr_number','invoice_number','vehicle_number')


def scan_context(instruction, user, branches):
    return (str(instruction or '') + '\nOperator login: ' + user +
            '. Allowed operational branches: ' + ', '.join(branches) +
            ('. This login is restricted to branch ' + branches[0] + '; use that branch.' if len(branches)==1 else
             '. Select a branch only when evidence identifies it; do not guess from a bank address.'))


def match_saved_vehicle(value, known):
    value = canonical_vehicle_number(value)
    fleet = {canonical_vehicle_number(v) for v in known} - {''}
    if not value or value in fleet:
        return value
    groups = ('0OQ','1IL','2Z','5S','8B','6G')
    def same_glyph(a,b):
        return a==b or any(a in group and b in group for group in groups)
    candidates = [v for v in fleet if (len(value)==4 and v[-4:].isdigit()
                  and all(same_glyph(a,b) for a,b in zip(v[-4:],value))) or
                  (len(v)==len(value) and sum(a!=b for a,b in zip(v,value))<=2
                   and all(same_glyph(a,b) for a,b in zip(v,value)))]
    return candidates[0] if len(candidates)==1 else value


def recover_entry_fields(result, extractor, api_key, context, files, model, branches, known_vehicles):
    if not result.rows:
        # A missing first row can still be recovered from an invoice on one targeted pass.
        row = None
    else:
        row = result.rows[0]
    if row is not None:
        if len(branches)==1:
            row.branch = branches[0]
        elif row.branch:
            row.branch = canonical_branch(row.branch) if canonical_branch(row.branch) in branches else ''
        if not row.invoice_number and row.invoice_numbers:
            row.invoice_number = row.invoice_numbers[0]
    missing = [field for field in PRIORITY_FIELDS if row is None or not str(getattr(row,field,'') or '').strip()]
    if row is not None and 'saintgobain' in re.sub(r'[^a-z]', '', row.company_name.lower()) and len(row.invoice_numbers) < 2:
        missing.append('invoice_numbers')
    parsed_date = parse_dtr_date(row.date) if row is not None else None
    if parsed_date is None or parsed_date.year < 2026:
        missing.append('date')
    visual = any(str(item.get('mime_type') or '').startswith('image/') or item.get('mime_type')=='application/pdf' for item in files)
    if missing and visual:
        current = row.model_dump() if row is not None else {}
        prompt = (context + '\nTargeted second reading of this same trip. Reinspect missing fields: ' + ', '.join(missing) +
                  '. Inspect labels, rotated text, dispatch/delivery addresses, and handwritten vehicle registration. '
                  'Keep already extracted fields unchanged. Do not copy LR to invoice or vice versa. '
                  'Do not invent unreadable values. Current extracted fields: ' + json.dumps(current,default=str))
        prompt += ('\nRead the printed Invoice Date/Date in the invoice header, including all four year digits. '
                   'Prefer this over product batch/manufacturing dates, delivery stamps and fiscal-year codes. '
                   'Return ISO YYYY-MM-DD. Recheck a missing, invalid or pre-2026 date from the image; '
                   'never replace its year merely to fit the current year. For example 22-10-2026 is 2026-10-22.')
        prompt += ('\nFor Saint-Gobain/Gyproc, recheck every row of the Invoice No column in the materials table. '
                   'One photo may contain multiple invoices for the same LR; return every distinct printed invoice '
                   'in invoice_numbers. Do not use Shipment No or invent a second number if only one is printed.')
        # Only relevant plate candidates are hints, never evidence for a route or document identifier.
        raw_vehicle = str(current.get('vehicle_number') or '')
        candidates = sorted({canonical_vehicle_number(v) for v in known_vehicles
                             if raw_vehicle and canonical_vehicle_number(v).endswith(canonical_vehicle_number(raw_vehicle)[-4:])})
        if not raw_vehicle:
            candidates = sorted({canonical_vehicle_number(v) for v in known_vehicles} - {''})[:200]
        if candidates:
            prompt += '\nSaved vehicle hints (not exhaustive; use only if visible registration supports a unique match, never choose arbitrarily): ' + ', '.join(candidates[:200])
        try:
            second, _ = extractor(api_key,'ENTRY',prompt,files,model,high_detail=True)
            if second.rows:
                if row is None:
                    result.rows = [second.rows[0]]
                    row = result.rows[0]
                else:
                    for field in missing:
                        value = getattr(second.rows[0],field,'')
                        if value:
                            setattr(row,field,value)
                    if 'invoice_number' in missing and second.rows[0].invoice_numbers:
                        row.invoice_numbers = second.rows[0].invoice_numbers
                    if not row.invoice_numbers and row.invoice_number:
                        row.invoice_numbers = [row.invoice_number]
        except Exception:
            # Preserve the successful first pass if optional rereading is unavailable.
            pass
    if row is not None:
        row.branch = branches[0] if len(branches)==1 else (canonical_branch(row.branch) if canonical_branch(row.branch) in branches else '')
        raw_vehicle = row.vehicle_number
        row.vehicle_number = match_saved_vehicle(raw_vehicle, known_vehicles)
        if canonical_vehicle_number(raw_vehicle) != row.vehicle_number:
            row.review_notes = (row.review_notes + f' Vehicle matched to saved registration {row.vehicle_number}; please verify.').strip()
    return result
