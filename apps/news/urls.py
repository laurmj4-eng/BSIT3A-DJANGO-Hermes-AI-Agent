from django.urls import path

from . import views

app_name = 'news'

urlpatterns = [
    path('', views.news_page, name='news_list'),
    path('refresh/', views.news_refresh, name='news_refresh'),
    path('save/<int:pk>/', views.news_toggle_save, name='news_toggle_save'),
]