"""URL configuration for mysite project.

Public site:
    /          dashboard (landing page)
    /news/     AI news feed

There is no admin panel mounted: nothing is exposed at /admin/.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from mysite import seo
from apps.core import views as core_views

urlpatterns = [
    path('', include('apps.core.urls')),
    path('news/', include('apps.news.urls')),
    path('robots.txt', seo.robots_txt, name='robots_txt'),
    path('sitemap.xml', seo.sitemap_xml, name='sitemap_xml'),
    path('sw.js', core_views.service_worker, name='service_worker'),
    path('offline.html', core_views.offline_page, name='offline_page'),
]

handler404 = 'mysite.error_views.custom_404'
handler500 = 'mysite.error_views.custom_500'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
