from django.urls import path
from .views import DashboardView
from . import views

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    
    path('country/', views.country_list, name='country_list'),
    path('country/create/', views.country_create, name='country_create'),
    path('country/edit/<uuid:id>/', views.country_edit, name='country_edit'),
    path('country/delete/<uuid:id>/', views.country_delete, name='country_delete'),
    
    path('state/', views.state_list, name='state_list'),
    path('state/create/', views.state_create, name='state_create'),
    path('state/edit/<uuid:id>/', views.state_edit, name='state_edit'),
    path('state/delete/<uuid:id>/', views.state_delete, name='state_delete'),
    
    path('district/', views.district_list, name='district_list'),
    path('district/create/', views.district_create, name='district_create'),
    path('district/edit/<uuid:id>/', views.district_edit, name='district_edit'),
    path('district/delete/<uuid:id>/', views.district_delete, name='district_delete'),
]
