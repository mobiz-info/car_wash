from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    path('client/', views.client_list, name='client_list'),
    path('client/create/', views.client_create, name='client_create'),
    path('client/edit/<uuid:id>/', views.client_edit, name='client_edit'),
    path('client/delete/<uuid:id>/', views.client_delete, name='client_delete'),
    path('ajax/states/', views.ajax_get_states, name='ajax_get_states'),
    path('ajax/areas/', views.ajax_get_areas, name='ajax_get_areas'),
    path('ajax/district/', views.ajax_get_districts, name='ajax_get_districts'),
    
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
    path('customer/edit/<uuid:id>/', views.customer_edit, name='customer_edit'),
    path('customer/delete/<uuid:id>/', views.customer_delete, name='customer_delete'),
    path('ajax/load-vehicle-models/', views.ajax_load_vehicle_models, name='ajax_load_vehicle_models'),

    # Scheme Management
    path('scheme/', views.scheme_list, name='scheme_list'),
    path('scheme/usages/', views.scheme_usage_list, name='scheme_usage_list'),
    path('scheme/create/', views.scheme_create, name='scheme_create'),
    path('scheme/edit/<uuid:id>/', views.scheme_edit, name='scheme_edit'),
    path('scheme/delete/<uuid:id>/', views.scheme_delete, name='scheme_delete'),
    path('scheme/detail/<uuid:id>/', views.scheme_detail, name='scheme_detail'),
    path('scheme/<uuid:scheme_id>/voucher/add/', views.voucher_add, name='voucher_add'),
    path('voucher/delete/<uuid:voucher_id>/', views.voucher_delete, name='voucher_delete'),

    # Vehicle Management
    path('customer-vehicle/', views.customer_vehicle_list, name='customer_vehicle_list'),
    path('customer-vehicle/create/', views.customer_vehicle_create, name='customer_vehicle_create'),
    path('customer-vehicle/edit/<uuid:pk>/', views.customer_vehicle_edit, name='customer_vehicle_edit'),
    path('customer-vehicle/delete/<uuid:pk>/', views.customer_vehicle_delete, name='customer_vehicle_delete'),

    # Mobile API Endpoints
    path('api/login/', api_views.api_login, name='api_login'),
    path('api/customer/search/', api_views.api_customer_search, name='api_customer_search'),
    path('api/invoice/services/', api_views.api_get_services, name='api_get_services'),
    path('api/invoice/create/', api_views.api_create_invoice, name='api_create_invoice'),
    path('api/customer/form-data/', api_views.api_get_form_data, name='api_get_form_data'),
    path('api/customer/add/', api_views.api_add_customer, name='api_add_customer'),
    path('api/customer/list/', api_views.api_list_customers, name='api_list_customers'),
    path('api/customer/get/', api_views.api_get_customer, name='api_get_customer'),
    path('api/customer/edit/', api_views.api_edit_customer, name='api_edit_customer'),
    path('api/vehicle/search/', api_views.api_vehicle_search, name='api_vehicle_search'),
    path('api/dashboard/stats/', api_views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/company/branches/', api_views.api_company_branches, name='api_company_branches'),
    path('api/schemes/available/', api_views.api_available_schemes, name='api_available_schemes'),
    path('api/schemes/branch/', api_views.api_branch_schemes, name='api_branch_schemes'),
    path('api/schemes/options/', api_views.api_scheme_options, name='api_scheme_options'),
    path('api/schemes/create/', api_views.api_create_scheme, name='api_create_scheme'),
    path('api/schemes/validate-voucher/', api_views.api_validate_voucher, name='api_validate_voucher'),

    # Reports
    path('api/reports/jobs/', api_views.api_report_jobs, name='api_report_jobs'),
    path('api/reports/scheme-beneficiary/', api_views.api_report_scheme_beneficiary, name='api_report_scheme_beneficiary'),
    path('api/reports/collection/', api_views.api_report_collection, name='api_report_collection'),
    path('api/reports/outstanding/', api_views.api_report_outstanding, name='api_report_outstanding'),
    path('api/reports/bookings/', api_views.api_report_bookings, name='api_report_bookings'),
    path('api/reports/cancellations/', api_views.api_report_cancellations, name='api_report_cancellations'),

    # Complaint Management
    path('api/complaint-types/', api_views.api_list_complaint_types, name='api_list_complaint_types'),
    path('api/complaint-types/create/', api_views.api_create_complaint_type, name='api_create_complaint_type'),
    path('api/complaints/create/', api_views.api_create_complaint, name='api_create_complaint'),
    path('api/complaints/list/', api_views.api_list_complaints, name='api_list_complaints'),
    path('api/complaints/update-status/', api_views.api_update_complaint_status, name='api_update_complaint_status'),

    # Complaint Web views
    path('complaint/', views.complaint_list, name='complaint_list'),
    path('complaint/create/', views.complaint_create, name='complaint_create'),
    path('complaint/resolve/<uuid:id>/', views.complaint_resolve, name='complaint_resolve'),
    path('complaint/type/create/', views.complaint_type_create, name='complaint_type_create'),

    # Company Web Settings (WhatsApp & Template)
    path('settings/whatsapp/', views.whatsapp_settings, name='whatsapp_settings'),
    path('settings/templates/', views.whatsapp_template_list, name='whatsapp_template_list'),
    path('settings/templates/create/', views.whatsapp_template_create, name='whatsapp_template_create'),
    path('settings/templates/edit/<uuid:id>/', views.whatsapp_template_edit, name='whatsapp_template_edit'),
    path('settings/templates/delete/<uuid:id>/', views.whatsapp_template_delete, name='whatsapp_template_delete'),
    
    path('customer-ledger/',views.customer_ledger,name='customer_ledger'),
    path('inactive-customer-report/',views.inactive_customer_report,name='inactive_customer_report'),
    
]
