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
]
