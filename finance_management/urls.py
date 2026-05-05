from django.urls import path
from . import views

urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('api/invoice/list/', views.api_list_invoices, name='api_list_invoices'),
]
