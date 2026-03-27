from __future__ import annotations
import re


# ── Formatting ────────────────────────────────────────────────────────────────

def fmt_hhmmss(seconds: float) -> str:
    """Format a signed duration as ±HH:MM:SS.

    Examples
    --------
    >>> fmt_hhmmss(3661)
    '01:01:01'
    >>> fmt_hhmmss(-90)
    '-00:01:30'
    """
    neg = seconds < 0
    s   = abs(int(seconds))
    return f"{'-' if neg else ''}{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def fmt_hhmm(seconds: float) -> str:
    """Format a signed duration as ±HH:MM (no seconds).

    Examples
    --------
    >>> fmt_hhmm(3661)
    '01:01'
    >>> fmt_hhmm(-90)
    '-00:01'
    """
    neg = seconds < 0
    s   = abs(int(seconds))
    return f"{'-' if neg else ''}{s // 3600:02d}:{(s % 3600) // 60:02d}"


def fmt_hhmm_nova(seconds: float) -> str:
    """Format a signed duration in NovaTime style: ±H,MM.

    NovaTime uses a comma as separator and always shows the sign.

    Examples
    --------
    >>> fmt_hhmm_nova(-16620)
    '-4,37'
    >>> fmt_hhmm_nova(3600)
    '+1,00'
    """
    neg = seconds < 0
    s   = abs(int(seconds))
    h   = s // 3600
    m   = (s % 3600) // 60
    return f"{'-' if neg else '+'}{h},{m:02d}"


# ── Decomposition ─────────────────────────────────────────────────────────────

def seconds_to_hms(seconds: float) -> tuple[int, int, int]:
    """Return (hours, minutes, seconds) from a non-negative duration in seconds.

    The input is treated as an absolute value so callers don't need to abs()
    before decomposing for display.

    Examples
    --------
    >>> seconds_to_hms(3661)
    (1, 1, 1)
    >>> seconds_to_hms(-90)
    (0, 1, 30)
    """
    s = abs(int(seconds))
    return s // 3600, (s % 3600) // 60, s % 60


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_nova_saldo(raw: str) -> float | None:
    """Parse a NovaTime saldo string into signed seconds.

    Handles:
    - Minutes format  : ``"Saldo: -274 Min"``
    - Hours format    : ``"Saldo:  -4,57 Std"``  (comma = HH,MM, **not** decimal)
    - Bare number     : ``"Saldo: 1.5"``          (assumed hours, prints a warning)

    Returns ``None`` when the string cannot be parsed.
    """
    # Minutes: "Saldo: -274 Min"
    m = re.search(r"Saldo:\s*([-+]?\d+[,.]?\d*)\s*Min", raw, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ".")) * 60

    # Hours HH,MM: "Saldo:  -4,57 Std"  →  -(4h 57min)
    m = re.search(r"Saldo:\s*([-+]?)(\d+)[,.](\d+)\s*Std", raw, re.IGNORECASE)
    if m:
        sign    = -1 if m.group(1) == "-" else 1
        hours   = int(m.group(2))
        minutes = int(m.group(3))
        return sign * (hours * 3600 + minutes * 60)

    # Fallback bare number — assume decimal hours
    m = re.search(r"Saldo:\s*([-+]?\d+[,.]?\d*)", raw)
    if m:
        val = float(m.group(1).replace(",", "."))
        print(f"[TimeUtils] No unit found in saldo string, assuming hours: {val}")
        return val * 3600

    return None