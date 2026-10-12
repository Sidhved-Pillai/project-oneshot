"""Shared canonical operational branch labels."""
def canonical_branch(value):
    original = ' '.join(str(value or '').split()).strip()
    known = {'andheri': 'Andheri', 'pune': 'Pune', 'wada': 'Wada',
             'vadodara': 'Vadodara', 'vadodra': 'Vadodara', 'baroda': 'Vadodara'}
    return known.get(original.casefold(), original)
