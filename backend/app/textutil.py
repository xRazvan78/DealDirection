"""Text helpers shared by search, import and receipt matching."""

import unicodedata


def fold(text: str) -> str:
    """Lowercase text and strip diacritics, so `Brânză` compares equal to `branza`."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower()
