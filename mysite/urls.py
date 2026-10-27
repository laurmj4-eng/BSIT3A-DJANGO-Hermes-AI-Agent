"""URL configuration for mysite project.

Public site:
    /          dashboard (landing page)
    /news/     AI news feed

There is no admin panel mounted: nothing is exposed at /admin/.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path('', include('apps.core.urls')),
    path('news/', include('apps.news.urls')),
]

handler404 = 'mysite.error_views.custom_404'
handler500 = 'mysite.error_views.custom_500'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
