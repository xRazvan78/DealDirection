"""Text helpers shared by the documents unit. Owner: Member 3, Task 10.

fold() matches the planned app.textutil.fold (Member 2, Task 1). Once that
exists, this can import it instead.
"""

import unicodedata


def fold(text: str) -> str:
    """Lowercase and strip diacritics: "Brânză de Țară" -> "branza de tara"."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())
