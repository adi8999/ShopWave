"""
app/security/sanitize.py
────────────────────────
PII-redaction and prompt-sanitization utilities for ShopWave.

Usage
-----
from app.security.sanitize import sanitize_search_query, redact_pii

safe_q   = sanitize_search_query(raw_input)   # use before DB search / AI call
clean_log = redact_pii(log_line)              # scrub before storing logs
"""
from __future__ import annotations

import re
import unicodedata
import html

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_QUERY_LEN = 300  # Hard cap on any search / AI prompt input

# PII patterns (compiled once at import time for performance)
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I), "[EMAIL]"),
    # US/intl phone numbers  (+1-800-555-0100 · (800) 555-0100 · 8005550100)
    (re.compile(r"(\+?\d[\d\s\-().]{7,}\d)", re.I), "[PHONE]"),
    # Credit / debit card numbers (13–19 digits, optionally spaced/dashed)
    (re.compile(r"\b(?:\d[ \-]?){13,19}\b"), "[CARD]"),
    # SSN (US)  123-45-6789 · 123 45 6789
    (re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"), "[SSN]"),
    # IPv4 addresses
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
    # JWT / Bearer tokens (long base64url strings)
    (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]*"), "[TOKEN]"),
    # API keys (generic long hex/alphanumeric, 32+ chars)
    (re.compile(r"\b[A-Za-z0-9]{32,}\b"), "[API_KEY]"),
]

# Prompt-injection / jailbreak trigger phrases (case-insensitive)
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.I)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions?",
        r"forget\s+(everything|all|your\s+instructions?)",
        r"you\s+are\s+now\s+(a|an|the)\s+",
        r"act\s+as\s+(a|an|the)\s+",
        r"jailbreak",
        r"dan\s+mode",
        r"developer\s+mode",
        r"sudo\s+mode",
        r"override\s+(system|safety|content)\s+(prompt|filter|policy)",
        r"disregard\s+your\s+training",
        r"reveal\s+(your\s+)?(system\s+prompt|instructions?|api\s+key)",
        r"output\s+raw\s+(json|xml|sql|html|code)",
        r"<\s*script[^>]*>",          # XSS script tags
        r"javascript\s*:",             # JS pseudo-protocol
        r"on\w+\s*=\s*[\"']",         # inline event handlers
        r"--\s*$",                     # SQL comment suffix
        r";\s*(drop|delete|truncate|alter|insert|update)\s+",  # SQL injection
        r"union\s+select",
        r"sleep\s*\(\s*\d+\s*\)",     # SQL time-based blind injection
    ]
]

# Allow-list: only these characters are permitted in search queries after normalization
_ALLOWED_QUERY_RE = re.compile(r"[^a-zA-Z0-9\s\-_,.'\"&$%#@!()?]")


# ── Core Helpers ──────────────────────────────────────────────────────────────


def _normalize_unicode(text: str) -> str:
    """Normalize unicode to NFC and strip non-printable / control characters."""
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities to neutralize XSS payloads."""
    # Unescape HTML entities first (catches &lt;script&gt; etc.)
    text = html.unescape(text)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    return text


def _truncate(text: str, max_len: int = MAX_QUERY_LEN) -> str:
    return text[:max_len]


# ── Public API ────────────────────────────────────────────────────────────────


def sanitize_search_query(raw: str) -> str:
    """
    Sanitize a raw customer search query before it is passed to the database
    full-text search or any external AI / vector model.

    Steps applied (in order):
        1. Truncate to MAX_QUERY_LEN
        2. Normalize unicode & strip control characters
        3. Strip HTML tags / decode HTML entities
        4. Detect and raise ValueError on prompt-injection patterns
        5. Remove disallowed characters via allow-list
        6. Collapse whitespace

    Returns
    -------
    str
        The cleaned, safe query string.

    Raises
    ------
    ValueError
        If a prompt-injection or jailbreak attempt is detected.
    """
    if not isinstance(raw, str):
        raise TypeError(f"Expected str, got {type(raw).__name__}")

    text = _truncate(raw.strip())
    text = _normalize_unicode(text)
    text = _strip_html(text)

    # Check for injection/jailbreak attempts
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                f"Blocked: potentially unsafe input detected. Pattern: {pattern.pattern!r}"
            )

    # Apply character allow-list
    text = _ALLOWED_QUERY_RE.sub("", text)

    # Collapse multiple whitespace
    text = " ".join(text.split())

    return text


def redact_pii(text: str) -> str:
    """
    Replace PII tokens (email, phone, card numbers, SSN, IPs, tokens, API keys)
    with placeholder tags. Safe to call on log lines before writing to disk.

    Parameters
    ----------
    text : str
        Raw text that may contain PII.

    Returns
    -------
    str
        Text with PII replaced by bracketed tags, e.g. ``[EMAIL]``, ``[PHONE]``.
    """
    if not isinstance(text, str):
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_ai_context(user_message: str, max_len: int = 500) -> str:
    """
    Prepare a user message for inclusion in an AI model prompt.

    Combines ``sanitize_search_query`` + PII redaction, then re-truncates to
    ``max_len`` characters (default 500) to limit token spend.

    Raises ValueError on injection attempts (caller should return HTTP 400).
    """
    clean = sanitize_search_query(user_message)
    clean = redact_pii(clean)
    return _truncate(clean, max_len)
