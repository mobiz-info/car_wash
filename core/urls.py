from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/edit/<uuid:pk>/', views.role_edit, name='role_edit'),
    path('roles/delete/<uuid:pk>/', views.role_delete, name='role_delete'),
    
    path('logs/', views.log_list, name='log_list'),
]
