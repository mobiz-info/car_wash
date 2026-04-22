from django.urls import path
from .views import DashboardView
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/roles/', views.role_list, name='role_list'),
    path('users/roles/create/', views.role_create, name='role_create'),
    path('users/roles/edit/<uuid:pk>/', views.role_edit, name='role_edit'),
    path('users/roles/delete/<uuid:pk>/', views.role_delete, name='role_delete'),

    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
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
    
    path('area/', views.area_list, name='area_list'),
    path('area/create/', views.area_create, name='area_create'),
    path('area/edit/<uuid:id>/', views.area_edit, name='area_edit'),
    path('area/delete/<uuid:id>/', views.area_delete, name='area_delete'),
    
    path('client/', views.client_list, name='client_list'),
    path('client/create/', views.client_create, name='client_create'),
    path('client/edit/<uuid:id>/', views.client_edit, name='client_edit'),
    path('client/delete/<uuid:id>/', views.client_delete, name='client_delete'),
]
