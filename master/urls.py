from django.urls import path
from . import views

urlpatterns = [
    # Country
    path('country/', views.country_list, name='country_list'),
    path('country/create/', views.country_create, name='country_create'),
    path('country/edit/<uuid:id>/', views.country_edit, name='country_edit'),
    path('country/delete/<uuid:id>/', views.country_delete, name='country_delete'),
    
    # State
    path('state/', views.state_list, name='state_list'),
    path('state/create/', views.state_create, name='state_create'),
    path('state/edit/<uuid:id>/', views.state_edit, name='state_edit'),
    path('state/delete/<uuid:id>/', views.state_delete, name='state_delete'),
    
    # District
    path('district/', views.district_list, name='district_list'),
    path('district/create/', views.district_create, name='district_create'),
    path('district/edit/<uuid:id>/', views.district_edit, name='district_edit'),
    path('district/delete/<uuid:id>/', views.district_delete, name='district_delete'),
    
    # Area
    path('area/', views.area_list, name='area_list'),
    path('area/create/', views.area_create, name='area_create'),
    path('area/edit/<uuid:id>/', views.area_edit, name='area_edit'),
    path('area/delete/<uuid:id>/', views.area_delete, name='area_delete'),
    
    path('vehicle-type/', views.vehicle_type_list, name='vehicle_type_list'),
    path('vehicle-type/create/', views.vehicle_type_create, name='vehicle_type_create'),
    path('vehicle-type/edit/<uuid:id>/', views.vehicle_type_edit, name='vehicle_type_edit'),
    path('vehicle-type/delete/<uuid:id>/', views.vehicle_type_delete, name='vehicle_type_delete'),
    
]
