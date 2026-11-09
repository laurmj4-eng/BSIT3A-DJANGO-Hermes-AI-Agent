"""Template helpers for the news feed."""

import math
import re

from django import template
from django.http import QueryDict
from django.utils.html import strip_tags

register = template.Library()

_WORD_RE = re.compile(r"\w+", re.UNICODE)


@register.filter(name="read_time")
def read_time(value):
    """Estimate reading time for a snippet of (possibly HTML) text.

    Tags are stripped, words are counted, and the result is rounded up at a
    200 words-per-minute pace with a floor of one minute.
    """
    text = strip_tags(str(value or ""))
    words = len(_WORD_RE.findall(text))
    minutes = max(1, math.ceil(words / 200))
    return f"{minutes} min read"


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Return the current query string with ``kwargs`` merged in.

    The ``page`` parameter is always dropped so links can safely reset
    pagination. Passing ``None`` or ``""`` removes a parameter instead of
    setting it. Works even when no ``request`` is in the context.
    """
    request = context.get("request")
    params = request.GET.copy() if request is not None else QueryDict(mutable=True)
    params.pop("page", None)
    for key, value in kwargs.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
