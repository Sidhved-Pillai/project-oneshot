VIJAY_TRANSPORTER_PROFILES = {
    "Altaf Khan Transport": {
        "beneficiary_name": "Altaf Khan Transport",
        "transporter_name": "Altaf Khan Transport",
        "beneficiary_account_number": "60350673934",
        "beneficiary_ifsc_code": "MAHB0000979",
    },
    "Nisar Anwar Shaikh": {
        "beneficiary_name": "Nisar Anwar Shaikh",
        "transporter_name": "Nisar Anwar Shaikh",
        "beneficiary_account_number": "917020048356986",
        "beneficiary_ifsc_code": "UTIB0002168",
    },
}

VIJAY_FREIGHT_RATES = {
    3844: 3270,
    4509: 3862,
    5073: 4300,
    6509: 5500,
    8748: 7440,
    10160: 8640,
    4327: 3680,
}


def vijay_transporter_profile(name):
    """Return a copy so form state cannot mutate the fixed profile."""
    return dict(VIJAY_TRANSPORTER_PROFILES.get(str(name or "").strip(), {}))


def vijay_transporter_freight(revenue):
    try:
        return VIJAY_FREIGHT_RATES.get(int(float(revenue)))
    except (TypeError, ValueError):
        return None
