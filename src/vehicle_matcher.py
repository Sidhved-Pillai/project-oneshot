from .remark_parser import normalize_vehicle, normalize_vehicle_type


def _active(master):
    if "Vehicle Status" not in master: return master
    return master[master["Vehicle Status"].fillna("Active").astype(str).str.lower().eq("active")]


def find_vehicle(identifier, master):
    ident = normalize_vehicle(identifier)
    if not ident: return []
    active = _active(master)
    if len(ident) == 4 and ident.isdigit():
        matches = active[active["Last 4 Digits"].astype(str).str.zfill(4) == ident]
    else:
        matches = active[active["Vehicle No."].map(normalize_vehicle) == ident]
    return matches.to_dict("records")


def vehicle_choices(identifiers, master):
    choices = []
    for identifier in identifiers:
        matches = find_vehicle(identifier, master)
        choices.extend(str(x.get("Vehicle No.", "")) for x in matches if x.get("Vehicle No."))
    return list(dict.fromkeys(choices))


def resolve_vehicle(identifiers, master):
    choices = vehicle_choices(identifiers, master)
    if len(choices) == 1:
        match = find_vehicle(choices[0], master)[0]
        return choices[0], match, choices
    unresolved = identifiers[0] if len(identifiers) == 1 else ""
    return unresolved, {}, choices


def choose_vehicle_type(remark_type, master_type):
    remark_type = normalize_vehicle_type(remark_type)
    master_type = normalize_vehicle_type(master_type)
    if remark_type: return remark_type, bool(master_type and master_type != remark_type)
    return master_type, False
