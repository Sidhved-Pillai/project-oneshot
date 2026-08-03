import re


def normalize_account(value):
    if value is None:
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return re.sub(r"\s+", "", text)


def find_beneficiary(account, master):
    target = normalize_account(account)
    matches = master[master["Beneficiary Account No."].map(normalize_account) == target]
    return matches.to_dict("records")

