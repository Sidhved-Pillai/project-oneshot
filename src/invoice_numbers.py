import re


def normalized_invoice_numbers(values):
    """Return distinct invoice identifiers in their supplied order."""
    result = []
    for value in values or []:
        cleaned = re.sub(r"\s+", "", str(value or "")).strip("/")
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def combined_invoice_number(values):
    """Store multiple invoices in the existing DTR-compatible text column."""
    return " / ".join(normalized_invoice_numbers(values))


def user_invoice_duplicates(records, user_name, invoice_value):
    """Return the user's saved records sharing any entered invoice identifier."""
    entered = {
        re.sub(r"\s+", "", part).strip("/").casefold()
        for part in re.split(r"\s*/\s*", str(invoice_value or ""))
        if re.sub(r"\s+", "", part).strip("/")
    }
    if not entered:
        return []
    matches = []
    for record in records or []:
        if str(record.get("created_by") or "").strip() != str(user_name or "").strip():
            continue
        saved = {
            re.sub(r"\s+", "", part).strip("/").casefold()
            for part in re.split(r"\s*/\s*", str(record.get("invoice_number") or ""))
            if re.sub(r"\s+", "", part).strip("/")
        }
        if entered & saved:
            matches.append(record)
    return matches


def valid_bisleri_invoice_number(value):
    """Vijay's Bisleri invoice IDs are MUMCIN plus exactly nine digits."""
    cleaned = re.sub(r"\s+", "", str(value or "")).upper()
    return cleaned if re.fullmatch(r"MUMCIN\d{9}", cleaned) else ""


def verified_bisleri_invoice_numbers(values):
    return normalized_invoice_numbers(
        valid for value in (values or []) if (valid := valid_bisleri_invoice_number(value))
    )


def reconcile_sequential_invoice_series(values, known_values=()):
    """Repair one inconsistent series prefix only when saved history proves it.

    Vijay's same-trip invoices are sequential and share everything before the
    final three-digit counter. If OCR disagrees on that shared prefix, history
    must select one unique prefix; otherwise ``None`` prevents silent autofill.
    """
    invoices = normalized_invoice_numbers(values)
    if len(invoices) < 2:
        return invoices
    parsed = [re.fullmatch(r"([A-Za-z]+)(\d{6,})", value) for value in invoices]
    if not all(parsed):
        return invoices
    letter_prefixes = {match.group(1).upper() for match in parsed}
    numeric_parts = [match.group(2) for match in parsed]
    if len(letter_prefixes) != 1 or len({len(value) for value in numeric_parts}) != 1:
        return invoices
    counters = [int(value[-3:]) for value in numeric_parts]
    if len(set(counters)) != len(counters) or max(counters) - min(counters) != len(counters) - 1:
        return invoices
    series = [match.group(1).upper() + numeric[:-3] for match, numeric in zip(parsed, numeric_parts)]
    if len(set(series)) == 1:
        return invoices

    known = normalized_invoice_numbers(
        part
        for value in known_values
        for part in re.split(r"\s*/\s*", str(value or ""))
    )
    support = {candidate: sum(item.upper().startswith(candidate) for item in known) for candidate in set(series)}
    best_score = max(support.values(), default=0)
    winners = [candidate for candidate, score in support.items() if score == best_score]
    if best_score == 0 or len(winners) != 1:
        return None
    winner = winners[0]
    return [f"{winner}{counter:03d}" for counter in counters]
