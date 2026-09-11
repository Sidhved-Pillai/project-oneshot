from .vehicle_normalization import canonical_vehicle_number


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

VIJAY_VEHICLE_TRANSPORTERS = {
    **{vehicle: "Altaf Khan Transport" for vehicle in (
        "MH04LE8405", "MH04LE8403", "MH04LE8404", "MH04KU8597", "MH04LE8412",
        "MH04EY1805", "MH05AM1810", "MH17AG4504", "MH04HD4002", "MH04EL6824",
        "MH10Z3589", "MH05AM1855", "MH04HY7995", "MH48AG8549", "MH04HY8003",
        "MH04HY7996", "MH48AG8548", "MH48AG8551", "MH04HD3996", "MH04HD4001",
        "MH48AG8550", "MH04HY8002", "MH04HY7990", "MH04HY7998", "MH04HY8006",
        "MH04HY7997", "MH04LE8407", "MH04HY7993",
    )},
    **{vehicle: "Nisar Anwar Shaikh" for vehicle in (
        "MH48AG8552", "MH04FJ0928", "MH04HD4003", "MH04HD3997",
    )},
}


def vijay_transporter_profile(name):
    """Return a copy so form state cannot mutate the fixed profile."""
    return dict(VIJAY_TRANSPORTER_PROFILES.get(str(name or "").strip(), {}))


def vijay_transporter_freight(revenue):
    try:
        return VIJAY_FREIGHT_RATES.get(int(float(revenue)))
    except (TypeError, ValueError):
        return None


def vijay_transporter_for_vehicle(vehicle_number):
    return VIJAY_VEHICLE_TRANSPORTERS.get(canonical_vehicle_number(vehicle_number), "")
