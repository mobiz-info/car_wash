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
    
    path('client/', views.client_list, name='client_list'),
    path('client/create/', views.client_create, name='client_create'),
    path('client/edit/<uuid:id>/', views.client_edit, name='client_edit'),
    path('client/delete/<uuid:id>/', views.client_delete, name='client_delete'),
]
