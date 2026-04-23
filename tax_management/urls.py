from django.urls import path
from . import views

urlpatterns = [
    path('tax/', views.tax_list, name='tax_list'),
    path('tax/create/', views.tax_create, name='tax_create'),
    path('tax/edit/<int:id>/', views.tax_edit, name='tax_edit'),
    path('tax/delete/<int:id>/', views.tax_delete, name='tax_delete'),
]