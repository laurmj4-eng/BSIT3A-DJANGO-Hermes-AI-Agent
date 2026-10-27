"""Template helpers for the news feed."""

from django import template
from django.http import QueryDict

register = template.Library()


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
