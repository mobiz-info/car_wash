from django.urls import path
from .views import DashboardView
from . import views

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    
    path('country/', views.country_list, name='country_list'),
    path('country/create/', views.country_create, name='country_create'),
    path('country/edit/<uuid:id>/', views.country_edit, name='country_edit'),
    path('country/delete/<uuid:id>/', views.country_delete, name='country_delete'),
]
