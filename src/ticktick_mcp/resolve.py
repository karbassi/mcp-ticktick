from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from Levenshtein import distance as levenshtein_distance

# Only offer a "did you mean" suggestion when the typo is small; beyond a few
# edits the closest name is more likely noise than the user's intent.
_SUGGESTION_MAX_DISTANCE = 3

# TickTick IDs are long hex strings. Real list/tag names are never this shape,
# so a value matching it is treated as an ID and returned untouched.
_ID_MIN_HEX_LEN = 20


def _looks_like_id(value: str) -> bool:
    """True if the value has the shape of a TickTick hex ID rather than a name."""
    return len(value) >= _ID_MIN_HEX_LEN and all(c in "0123456789abcdefABCDEF" for c in value)


def _no_match_error(
    query: str,
    items: Sequence[Any],
    get_name: Callable[[Any], str],
    entity_type: str,
) -> ValueError:
    """Build the not-found error, appending a suggestion when a near miss exists.

    A misspelling should point the user at what they likely meant instead of
    leaving them to guess, but only when the closest name is within editing
    reach — otherwise the "suggestion" is just the alphabetically nearest noise.
    """
    message = f"No {entity_type} found matching '{query}'"
    search = query.lower()
    closest_name = ""
    closest_distance = float("inf")
    for item in items:
        distance = levenshtein_distance(search, get_name(item).lower())
        if distance < closest_distance:
            closest_distance = distance
            closest_name = get_name(item)
    if closest_distance <= _SUGGESTION_MAX_DISTANCE:
        message += f". Did you mean '{closest_name}'?"
    return ValueError(message)


def resolve_name(
    query: str,
    items: Sequence[Any],
    get_name: Callable[[Any], str],
    get_id: Callable[[Any], str],
    entity_type: str = "item",
) -> str:
    """Resolve a user-provided name or ID to an actual ID.

    Resolution order:
    1. If query looks like a hex ID, return as-is
    2. Exact name match (case-insensitive)
    3. Single substring match
    4. Ambiguous multiple matches error
    5. No match — raise, suggesting the closest name when it's a near miss

    Returns the resolved ID string.
    """
    if _looks_like_id(query):
        return query

    search = query.lower()

    for item in items:
        if get_name(item).lower() == search:
            return get_id(item)

    # Fall back to substring matching so partial names ("work" -> "Work stuff")
    # resolve, but refuse when it's ambiguous rather than guessing.
    matches = [item for item in items if search in get_name(item).lower()]

    if len(matches) == 1:
        return get_id(matches[0])

    if len(matches) > 1:
        names = [get_name(m) for m in matches]
        raise ValueError(
            f"Multiple {entity_type}s match '{query}': {', '.join(names)}. "
            f"Use a more specific name or the full ID."
        )

    raise _no_match_error(query, items, get_name, entity_type)


def resolve_name_with_etag(
    query: str,
    items: Sequence[Any],
    get_name: Callable[[Any], str],
    get_id: Callable[[Any], str],
    get_etag: Callable[[Any], str],
    entity_type: str = "item",
) -> tuple[str, str]:
    """Like resolve_name but also returns the etag needed for optimistic updates.

    Returns (id, etag).
    """
    # When given an ID directly we still scan for the item, because its etag is
    # required to update it later. An unknown ID yields an empty etag rather
    # than an error — the caller may be operating on something not yet listed.
    if _looks_like_id(query):
        for item in items:
            if get_id(item) == query:
                return get_id(item), get_etag(item)
        return query, ""

    search = query.lower()

    for item in items:
        if get_name(item).lower() == search:
            return get_id(item), get_etag(item)

    # Fall back to substring matching so partial names resolve, but refuse when
    # it's ambiguous rather than guessing.
    matches = [item for item in items if search in get_name(item).lower()]

    if len(matches) == 1:
        return get_id(matches[0]), get_etag(matches[0])

    if len(matches) > 1:
        names = [get_name(m) for m in matches]
        raise ValueError(
            f"Multiple {entity_type}s match '{query}': {', '.join(names)}. "
            f"Use a more specific name or the full ID."
        )

    raise _no_match_error(query, items, get_name, entity_type)
