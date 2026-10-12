"""Signed, expiring reconnect tokens bound to a member and their current code."""
import base64
import hashlib
import hmac
import os
import time

import streamlit as st


@st.cache_resource
def signing_key(configured):
    # Never derive a signing key from publicly visible code hashes.
    return configured.encode() if configured else os.urandom(32)


def issue_member_session(member, key, codes, now=None):
    expires = int(time.time() if now is None else now) + 7 * 24 * 60 * 60
    payload = f"{member}|{expires}".encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip('=')
    bound_key = hmac.new(key, codes[member].encode(), hashlib.sha256).digest()
    signature = hmac.new(bound_key, encoded.encode(), hashlib.sha256).hexdigest()
    return f'{encoded}.{signature}'


def restore_member_session(token, key, codes, now=None):
    try:
        encoded, supplied = token.split('.', 1)
        member, expiry = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode().split('|', 1)
        if member not in codes or int(expiry) < int(time.time() if now is None else now):
            return None
        bound_key = hmac.new(key, codes[member].encode(), hashlib.sha256).digest()
        expected = hmac.new(bound_key, encoded.encode(), hashlib.sha256).hexdigest()
        return member if hmac.compare_digest(expected, supplied) else None
    except (ValueError, TypeError, UnicodeError):
        return None
