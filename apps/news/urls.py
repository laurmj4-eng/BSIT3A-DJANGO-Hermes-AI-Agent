from django.urls import include, path

from . import views

app_name = 'news'

urlpatterns = [
    path('', views.news_page, name='news_list'),
    path('refresh/', views.news_refresh, name='news_refresh'),
    path('save/<int:pk>/', views.news_toggle_save, name='news_toggle_save'),
    path('read/<int:pk>/', views.news_toggle_read, name='news_toggle_read'),
    path('open/<int:pk>/', views.news_open, name='news_open'),
    path('image-proxy/', views.news_image_proxy, name='image_proxy'),
    path('export/<str:fmt>/', views.news_export, name='news_export'),
    path('rss/', views.news_rss, name='news_rss'),
    path('api/articles/', views.news_api, name='news_api'),
    path('api/suggest/', views.news_suggest, name='news_suggest'),
    path('sources/', include('apps.news.health_urls')),
]
