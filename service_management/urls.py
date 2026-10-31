from django.urls import path
from . import views

urlpatterns = [
    path('jobcard/<str:master>/', views.jobcard_master_list, name='jobcard_master_list'),
    path('jobcard/<str:master>/create/', views.jobcard_master_form, name='jobcard_master_create'),
    path('jobcard/<str:master>/edit/<uuid:id>/', views.jobcard_master_form, name='jobcard_master_edit'),
    path('jobcard/<str:master>/delete/<uuid:id>/', views.jobcard_master_delete, name='jobcard_master_delete'),
    path('jobcard/services/by-category/<uuid:category_id>/', views.jobcard_services_by_category, name='jobcard_services_by_category'),
    path('service-types/', views.service_type_list, name='service_type_list'),
    path('service-types/create/', views.service_type_create, name='service_type_create'),
    path('service-types/edit/<uuid:id>/', views.service_type_edit, name='service_type_edit'),
    path('service-types/delete/<uuid:id>/', views.service_type_delete, name='service_type_delete'),
    
    path('services/', views.service_list, name='service_list'),
    path('services/create/', views.service_create, name='service_create'),
    path('services/edit/<uuid:id>/', views.service_edit, name='service_edit'),
    path('services/delete/<uuid:id>/', views.service_delete, name='service_delete'),
    
    path('branch/services/', views.branch_service_list, name='branch_service_list'),
    path('company/services/', views.company_service_manage, name='company_service_manage'),
    path('branch/<uuid:branch_id>/services/', views.branch_service_manage, name='branch_service_manage'),

    path('branch/vehicle-prices/',views.branch_vehicle_price_list,name='branch_vehicle_price_list'),
    path('branch/<uuid:branch_id>/vehicle-price/create/',views.branch_vehicle_price_create,name='branch_vehicle_price_create'),

    path('branch/<uuid:branch_id>/service-pricing/', views.service_vehicle_price_manage, name='service_vehicle_price_manage'),
    path('branch/service-pricing/', views.service_vehicle_price_redirect, name='service_vehicle_price_redirect'),

    path('branch/<uuid:branch_id>/smoke-test-pricing/', views.smoke_test_price_manage, name='smoke_test_price_manage'),
    path('branch/smoke-test-pricing/', views.smoke_test_price_redirect, name='smoke_test_price_redirect'),
]
