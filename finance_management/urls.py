from django.urls import path
from . import views

urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('outstanding/', views.outstanding_list, name='outstanding_list'),
    path('outstanding/collect/<uuid:invoice_id>/', views.collect_payment, name='collect_payment'),
    path('api/invoice/list/', views.api_list_invoices, name='api_list_invoices'),

    # Sales & receipts (upstream)
    path('sales-report/', views.sales_report, name='sales_report'),
    path('invoice-receipt/<uuid:pk>/', views.invoice_receipt, name='invoice_receipt'),
    path('receipt-list/', views.receipt_list, name='receipt_list'),
    path('receipt-create/', views.receipt_create, name='receipt_create'),

    # Mobile APIs (stash)
    path('api/outstanding/list/', views.api_outstanding_list, name='api_outstanding_list'),
    path('api/outstanding/collect/', views.api_collect_payment, name='api_collect_payment'),
    path('api/receipt/list/', views.api_receipt_list, name='api_receipt_list'),
    
    path('reports/job-report/',views.job_report,name='job_report'),
    path('booking-report/', views.booking_report, name='booking_report'),
    path('cancellation-report/',views.cancellation_report,name='cancellation_report'),
    
]
