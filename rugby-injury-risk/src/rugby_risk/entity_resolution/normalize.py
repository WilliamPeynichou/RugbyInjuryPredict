"""Name normalisation shared by the anchor and Splink steps."""

import re
import unicodedata

PARTICLES = frozenset({"de", "du", "des", "da", "di", "del", "dos", "van", "von", "der", "den"})
PARTICLES |= frozenset({"le", "la", "ter"})
SUFFIXES = frozenset({"jr", "jnr", "junior", "sr", "snr"})


def normalize_name(name: str) -> str:
    """Lowercase ASCII tokens, particles and suffixes dropped, sorted (first/last order free)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    ascii_name = re.sub(r"[\u2019'`]", "", ascii_name)  # O'Mahony = OMahony
    tokens = re.sub(r"[^a-z]+", " ", ascii_name).split()
    return " ".join(sorted(t for t in tokens if t not in PARTICLES | SUFFIXES))


def name_block(name_norm: str) -> str:
    """Blocking prefix: first letter of the sorted normalised name."""
    return name_norm[:1]
