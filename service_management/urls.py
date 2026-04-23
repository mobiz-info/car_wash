from django.urls import path
from . import views

urlpatterns = [
    path('service-types/', views.service_type_list, name='service_type_list'),
    path('service-types/create/', views.service_type_create, name='service_type_create'),
    path('service-types/edit/<uuid:id>/', views.service_type_edit, name='service_type_edit'),
    path('service-types/delete/<uuid:id>/', views.service_type_delete, name='service_type_delete'),
    
    path('services/', views.service_list, name='service_list'),
    path('services/create/', views.service_create, name='service_create'),
    path('services/edit/<uuid:id>/', views.service_edit, name='service_edit'),
    path('services/delete/<uuid:id>/', views.service_delete, name='service_delete'),
]
