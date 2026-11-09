"""Anonymous reader profile persistence (Phase 2 F4).

Profiles are keyed by a signed, httponly cookie holding a UUID token.
No user FK, no email/name/IP — nothing that identifies a person.
"""

import uuid

from django.conf import settings
from django.core import signing
from django.utils import timezone

from apps.news.models import ReaderProfile

PROFILE_COOKIE = "hermes_reader"
COOKIE_MAX_AGE = 31536000  # 1 year, seconds

_ID_FIELDS = ("bookmarks", "read_ids")
_ID_CAP = 1000
_HISTORY_CAP = 200


def _sign_token(token) -> str:
    return signing.get_cookie_signer(salt=PROFILE_COOKIE).sign(str(token))


def set_profile_cookie(response, request):
    """Apply the pending signed profile cookie (set by get_reader_profile) to a response."""
    signed = getattr(request, "_reader_profile_cookie", None)
    if not signed:
        return response
    response.set_cookie(
        PROFILE_COOKIE,
        signed,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    return response


def get_reader_profile(request, create=False):
    """Return the ReaderProfile for the signed cookie, or None.

    With create=True, a missing/invalid cookie yields a fresh row and the
    signed cookie value is stashed on ``request._reader_profile_cookie``;
    call ``set_profile_cookie(response, request)`` to emit it.
    """
    raw = request.get_signed_cookie(PROFILE_COOKIE, default=None)
    profile = None
    if raw:
        try:
            token = uuid.UUID(str(raw))
        except (ValueError, AttributeError, TypeError):
            token = None
        if token is not None:
            try:
                profile = ReaderProfile.objects.filter(token=token).first()
            except Exception:
                profile = None
    if profile is None and create:
        profile = ReaderProfile.objects.create()
        request._reader_profile_cookie = _sign_token(profile.token)
    return profile


def _raw_list(profile, field):
    if profile is None:
        return []
    try:
        value = getattr(profile, field, None)
    except Exception:
        return []
    if not isinstance(value, list):
        return []
    return value


def _to_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            try:
                return int(text)
            except ValueError:
                return None
    return None


def ids(profile, field):
    """Sanitized list[int] from a JSON list field: ints only, deduped, order preserved."""
    out, seen = [], set()
    for item in _raw_list(profile, field):
        num = _to_int(item)
        if num is None or num in seen:
            continue
        seen.add(num)
        out.append(num)
    return out


def _save(profile, field):
    profile.save(update_fields=[field, "updated_at"])


def add_id(profile, field, value):
    """Insert value newest-first; bounded at 1000 for bookmarks/read_ids."""
    if profile is None:
        return []
    num = _to_int(value)
    current = ids(profile, field)
    if num is None:
        return current
    merged = [num] + [i for i in current if i != num]
    if field in _ID_FIELDS:
        merged = merged[:_ID_CAP]
    setattr(profile, field, merged)
    _save(profile, field)
    return merged


def remove_id(profile, field, value):
    if profile is None:
        return []
    num = _to_int(value)
    current = ids(profile, field)
    if num is None:
        return current
    merged = [i for i in current if i != num]
    setattr(profile, field, merged)
    _save(profile, field)
    return merged


def merge_ids(profile, field, values):
    """Merge legacy session IDs without a cap. Newest (given) first, deduped."""
    if profile is None:
        return []
    current = ids(profile, field)
    incoming = []
    for item in values or []:
        num = _to_int(item)
        if num is not None and num not in incoming:
            incoming.append(num)
    merged = incoming + [i for i in current if i not in incoming]
    if field in _ID_FIELDS:
        merged = merged[:_ID_CAP]
    setattr(profile, field, merged)
    _save(profile, field)
    return merged


def record_history(profile, pk):
    """Prepend {"id": int, "at": ISO8601}; dedupe by id; cap 200; newest first."""
    if profile is None:
        return []
    num = _to_int(pk)
    if num is None:
        return _history_entries(profile)
    entries = _history_entries(profile)
    seen, deduped = set(), []
    for entry in entries:
        if entry["id"] in seen:
            continue
        seen.add(entry["id"])
        deduped.append(entry)
    new_entry = {"id": num, "at": timezone.now().isoformat()}
    merged = [new_entry] + [e for e in deduped if e["id"] != num]
    merged = merged[:_HISTORY_CAP]
    profile.history = merged
    _save(profile, "history")
    return merged


def _history_entries(profile):
    out = []
    for item in _raw_list(profile, "history"):
        if not isinstance(item, dict):
            continue
        entry_id = _to_int(item.get("id"))
        at = item.get("at")
        if entry_id is None or not isinstance(at, str):
            continue
        out.append({"id": entry_id, "at": at})
    return out


def history_entries(profile):
    """Public sanitized list of history entries."""
    return _history_entries(profile)


_SEARCH_CAP = 20
_SEARCH_NAME_MAX = 80
_SEARCH_QUERY_MAX = 500


def saved_searches(profile):
    """Sanitized saved-search entries: str name/query, newest first, cap 20."""
    if profile is None:
        return []
    out = []
    for item in _raw_list(profile, "saved_searches"):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        query = item.get("query")
        if not isinstance(name, str) or not isinstance(query, str):
            continue
        name = name.strip()[:_SEARCH_NAME_MAX]
        query = query.strip()[:_SEARCH_QUERY_MAX]
        if not name or not query:
            continue
        out.append({"name": name, "query": query})
        if len(out) >= _SEARCH_CAP:
            break
    return out


def add_saved_search(profile, name, query):
    """Add a saved search; dedupe by query; newest first; cap 20."""
    if profile is None:
        return [], "Profile is required."
    if not isinstance(name, str) or not isinstance(query, str):
        return saved_searches(profile), "Name and query are required."
    name = name.strip()
    query = query.strip()
    if not name or not query:
        return saved_searches(profile), "Name and query are required."
    name = name[:_SEARCH_NAME_MAX]
    query = query[:_SEARCH_QUERY_MAX]
    current = saved_searches(profile)
    filtered = [entry for entry in current if entry["query"] != query]
    merged = [{"name": name, "query": query}] + filtered
    merged = merged[:_SEARCH_CAP]
    profile.saved_searches = merged
    _save(profile, "saved_searches")
    return merged, None


def remove_saved_search(profile, index):
    """Remove a saved search by 0-based index; invalid index ignored."""
    if profile is None:
        return []
    current = saved_searches(profile)
    num = _to_int(index)
    if num is None or num < 0 or num >= len(current):
        return current
    merged = [entry for i, entry in enumerate(current) if i != num]
    profile.saved_searches = merged
    _save(profile, "saved_searches")
    return merged
