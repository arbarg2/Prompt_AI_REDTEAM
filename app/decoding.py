"""Bounded decoding of encoded/obfuscated prompt text. Decoded text is only ever pattern-matched; never executed."""
from __future__ import annotations

import base64
import binascii
import codecs
import re
import unicodedata
import urllib.parse

_B64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_HEX = re.compile(r"(?:[0-9a-fA-F]{2}[\s:]?){8,}")
_ZW = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
_SPACED = re.compile(r"\b(?:[a-z][ .\-_]){3,}[a-z]\b")
MAX_CANDIDATES = 5


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_ZW)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def deobfuscate(norm: str) -> str:
    """Undo leetspeak and letter-spacing. Returns the input unchanged if nothing was obfuscated."""
    out = _SPACED.sub(lambda m: re.sub(r"[ .\-_]", "", m.group(0)), norm)
    return out.translate(_LEET)


def _printable(raw: bytes) -> str | None:
    try:
        s = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(s) < 6 or sum(c.isprintable() or c.isspace() for c in s) / len(s) < 0.95:
        return None
    return s


def decode_candidates(prompt: str, max_bytes: int = 2048) -> list[str]:
    """Return normalized decoded strings (single layer only) found in the prompt."""
    found: list[str] = []
    window = prompt[: max_bytes * 4]
    for m in _B64.finditer(window):
        tok = m.group(0)
        tok += "=" * (-len(tok) % 4)
        try:
            raw = base64.b64decode(tok, validate=True)[:max_bytes]
        except (binascii.Error, ValueError):
            continue
        if (s := _printable(raw)):
            found.append(s)
    for m in _HEX.finditer(window):
        try:
            raw = bytes.fromhex(re.sub(r"[\s:]", "", m.group(0)))[:max_bytes]
        except ValueError:
            continue
        if (s := _printable(raw)):
            found.append(s)
    low = window.lower()
    if "%" in window and re.search(r"%[0-9a-f]{2}", low):
        s = urllib.parse.unquote(window)
        if s != window:
            found.append(s)
    if "rot13" in low or "rot-13" in low or "caesar" in low:
        found.append(codecs.decode(window, "rot_13"))
    if re.search(r"\b(?:reversed|backwards?)\b", low):
        found.append(window[::-1])
    return [normalize(s) for s in found[:MAX_CANDIDATES]]
