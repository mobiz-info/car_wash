from django.urls import path
from . import views

urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('api/invoice/list/', views.api_list_invoices, name='api_list_invoices'),
    
    path('sales-report/', views.sales_report, name='sales_report'),
    path('invoice-receipt/<uuid:pk>/',views.invoice_receipt,name='invoice_receipt'),
    path('receipt-list/',views.receipt_list,name='receipt_list'),
    path('receipt-create/',views.receipt_create,name='receipt_create'),
    
    
]
