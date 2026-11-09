from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.home, name='dashboard'),
    # Keep old /home/ links working without a second view.
    path('home/', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
]
