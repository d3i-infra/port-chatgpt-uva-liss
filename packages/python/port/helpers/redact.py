"""
Redaction of PII from text: emails, Dutch postal codes, and phone numbers.

All three patterns are applied in a single pass over the string, making this
efficient even for large inputs.
"""

import re

REDACT_EMAIL = "[EMAIL]"
REDACT_PHONE = "[PHONE]"
REDACT_POSTAL_CODE = "[POSTAL_CODE]"

# ---------------------------------------------------------------------------
# Individual pattern strings (used both in the combined re and standalone fns)
# ---------------------------------------------------------------------------

_EMAIL_PAT = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"

# Dutch postal codes: 4 digits (no leading zero) + optional single space + 2 letters
_POSTAL_PAT = r"(?<!\d)[1-9][0-9]{3}[ ]?[A-Za-z]{2}(?!\w)"

# Phone numbers – possessive-style groups prevent catastrophic backtracking.
# Covers: +31 6 12345678 | 06-12345678 | (020) 1234567 | 0201234567 | +1-800-555-0100
_PHONE_PAT = (
    r"(?<![.\d])"
    r"(?:"
        # +31 followed by 9 digits, optional separators between groups
        r"\+31[-\s]?\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}"
    r"|"
        # (020) 1234567 — parens area code then 6–7 digit subscriber number
        r"\(0\d{1,3}\)[-\s]?\d{6,7}"
    r"|"
        # 0xxxxxxxxx — bare 10 digits, no separators (06-bare, 020-bare, etc.)
        r"0\d{9}"
    r"|"
        # 0x(x)(x)-xxxxxxx(x) — one separator, area (1–3 extra digits) + 6–8 subscriber digits
        r"0\d{1,3}[-\s.]\d{6,8}"
    r")"
    r"(?![.\d])"
)

# ---------------------------------------------------------------------------
# Single combined regex – one pass, named groups for dispatch
# ---------------------------------------------------------------------------

_COMBINED_RE = re.compile(
    rf"(?P<email>{_EMAIL_PAT})|(?P<postal>{_POSTAL_PAT})|(?P<phone>{_PHONE_PAT})",
    re.IGNORECASE,
)

_REPLACEMENTS: dict[str, str] = {
    "email": REDACT_EMAIL,
    "postal": REDACT_POSTAL_CODE,
    "phone": REDACT_PHONE,
}


def _replace(m: re.Match) -> str:  # type: ignore[type-arg]
    return _REPLACEMENTS[m.lastgroup]  # type: ignore[index]


def redact(text: str) -> str:
    """Redact emails, Dutch postal codes, and phone numbers from *text* in one pass."""
    return _COMBINED_RE.sub(_replace, text)


# ---------------------------------------------------------------------------
# Convenience single-type helpers (compile standalone patterns lazily)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(_EMAIL_PAT, re.IGNORECASE)
_POSTAL_RE = re.compile(_POSTAL_PAT, re.IGNORECASE)
_PHONE_RE = re.compile(_PHONE_PAT, re.IGNORECASE)


def redact_email(text: str) -> str:
    return _EMAIL_RE.sub(REDACT_EMAIL, text)


def redact_dutch_postal_code(text: str) -> str:
    return _POSTAL_RE.sub(REDACT_POSTAL_CODE, text)


def redact_phone(text: str) -> str:
    return _PHONE_RE.sub(REDACT_PHONE, text)
