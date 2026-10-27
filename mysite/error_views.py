"""Custom error views for Hermes AI News Agent.

Rendered via mysite.urls handler404 / handler500 (DEBUG=False).
Keep these views dependency-free: the 500 page must not touch the
database or the messages framework.
"""
from django.shortcuts import render


def custom_404(request, exception):
    return render(request, 'errors/404.html', status=404)


def custom_500(request):
    return render(request, 'errors/500.html', status=500)
