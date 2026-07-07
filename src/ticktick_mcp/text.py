from __future__ import annotations

import unicodedata
from typing import Any

# A list icon begins with a pictograph (Unicode category So). The run may then
# continue through joiners/modifiers: skin-tone modifiers (Sk), ZWJ (Cf),
# variation selectors (Mn), and keycap enclosers (Me). Keying off category —
# rather than fixed ranges — covers every emoji regardless of Unicode version.
# Sk is deliberately NOT a start category: skin-tone modifiers never lead a
# sequence, and Sk also contains plain text symbols like "^" (U+005E) and "`"
# (U+0060) that must not be mistaken for an icon. Real text (letters Lu/Ll,
# other letters Lo like CJK, digits Nd) is never in these sets, so it is kept.
_EMOJI_START = {"So"}
_EMOJI_CONT = {"So", "Sk", "Cf", "Mn", "Me"}


def strip_leading_emoji(name: str) -> str:
    """Remove a leading emoji icon (and any following whitespace) from a name.

    An icon is a leading run that starts with a pictograph (Unicode category
    ``So``); sequences that start with plain text — including symbols in category
    ``Sk`` such as ``^`` and keycap digits like ``1`` + U+FE0F + U+20E3 — are
    therefore left intact. No-op when the name has no such leading icon, so a
    plain name keeps its exact text (including any legitimate leading space).
    Inline emoji are kept. Falls back to the original if stripping would leave an
    empty string.
    """
    if not name or unicodedata.category(name[0]) not in _EMOJI_START:
        return name

    i = 0
    while i < len(name) and unicodedata.category(name[i]) in _EMOJI_CONT:
        i += 1

    rest = name[i:].lstrip()
    return rest if rest else name


def clean_project(project: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a project dict with its ``name`` icon stripped.

    Always returns a new dict; a missing or non-string ``name`` is copied through
    unchanged so callers never receive the original object.
    """
    name = project.get("name")
    if isinstance(name, str):
        return {**project, "name": strip_leading_emoji(name)}
    return {**project}
