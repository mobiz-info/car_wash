from django.urls import path
from . import views

urlpatterns = [
    path('client/', views.client_list, name='client_list'),
    path('client/create/', views.client_create, name='client_create'),
    path('client/edit/<uuid:id>/', views.client_edit, name='client_edit'),
    path('client/delete/<uuid:id>/', views.client_delete, name='client_delete'),
    path('ajax/states/', views.ajax_get_states, name='ajax_get_states'),
    path('ajax/areas/', views.ajax_get_areas, name='ajax_get_areas'),

    # Subscription
    path('subscription/', views.subscription_list, name='subscription_list'),
    path('subscription/create/', views.subscription_create, name='subscription_create'),
    path('subscription/edit/<uuid:id>/', views.subscription_edit, name='subscription_edit'),
    path('subscription/delete/<uuid:id>/', views.subscription_delete, name='subscription_delete'),

    # Branch Management
    path('branch/', views.branch_list, name='branch_list'),
    path('branch/create/', views.branch_create, name='branch_create'),
    path('branch/edit/<uuid:id>/', views.branch_edit, name='branch_edit'),
    path('branch/delete/<uuid:id>/', views.branch_delete, name='branch_delete'),

    # Staff Management
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/edit/<uuid:id>/', views.staff_edit, name='staff_edit'),
    path('staff/delete/<uuid:id>/', views.staff_delete, name='staff_delete'),
    
    # Customer Type
    path('customer-type/', views.customer_type_list, name='customer_type_list'),
    path('customer-type/create/', views.customer_type_create, name='customer_type_create'),
    path('customer-type/edit/<uuid:id>/', views.customer_type_edit, name='customer_type_edit'),
    path('customer-type/delete/<uuid:id>/', views.customer_type_delete, name='customer_type_delete'),

    # Customer Management
    path('customer/', views.customer_list, name='customer_list'),
    path('customer/create/', views.customer_create, name='customer_create'),
    path('ajax/load-vehicle-models/', views.ajax_load_vehicle_models, name='ajax_load_vehicle_models'),

    # Scheme Management
    path('scheme/', views.scheme_list, name='scheme_list'),
    path('scheme/create/', views.scheme_create, name='scheme_create'),
    path('scheme/delete/<uuid:id>/', views.scheme_delete, name='scheme_delete'),
    
    # Vehicle Management
    path('customer-vehicle/', views.customer_vehicle_list, name='customer_vehicle_list'),
    path('customer-vehicle/create/', views.customer_vehicle_create, name='customer_vehicle_create'),
    path('customer-vehicle/edit/<uuid:pk>/', views.customer_vehicle_edit, name='customer_vehicle_edit'),
    path('customer-vehicle/delete/<uuid:pk>/', views.customer_vehicle_delete, name='customer_vehicle_delete'),
]
