from django.urls import path
from . import views

urlpatterns = [
    # Country
    path('country/', views.country_list, name='country_list'),
    path('country/create/', views.country_create, name='country_create'),
    path('country/edit/<uuid:id>/', views.country_edit, name='country_edit'),
    path('country/delete/<uuid:id>/', views.country_delete, name='country_delete'),
    
    # State
    path('state/', views.state_list, name='state_list'),
    path('state/create/', views.state_create, name='state_create'),
    path('state/edit/<uuid:id>/', views.state_edit, name='state_edit'),
    path('state/delete/<uuid:id>/', views.state_delete, name='state_delete'),
    
    # District
    path('district/', views.district_list, name='district_list'),
    path('district/create/', views.district_create, name='district_create'),
    path('district/edit/<uuid:id>/', views.district_edit, name='district_edit'),
    path('district/delete/<uuid:id>/', views.district_delete, name='district_delete'),
    
    # Area
    path('area/', views.area_list, name='area_list'),
    path('area/create/', views.area_create, name='area_create'),
    path('area/edit/<uuid:id>/', views.area_edit, name='area_edit'),
    path('area/delete/<uuid:id>/', views.area_delete, name='area_delete'),
    
    path('vehicle-type/', views.vehicle_type_list, name='vehicle_type_list'),
    path('vehicle-type/create/', views.vehicle_type_create, name='vehicle_type_create'),
    path('vehicle-type/edit/<uuid:id>/', views.vehicle_type_edit, name='vehicle_type_edit'),
    path('vehicle-type/delete/<uuid:id>/', views.vehicle_type_delete, name='vehicle_type_delete'),
    
    path('vehicle-type-model/', views.vehicle_type_model_list, name='vehicle_type_model_list'),
    path('vehicle-type-model/create/', views.vehicle_type_model_create, name='vehicle_type_model_create'),
    path('vehicle-type-model/edit/<uuid:id>/', views.vehicle_type_model_edit, name='vehicle_type_model_edit'),
    path('vehicle-type-model/delete/<uuid:id>/', views.vehicle_type_model_delete, name='vehicle_type_model_delete'),
    path('vehicle-type-model/toggle-enable/<uuid:id>/', views.vehicle_type_model_toggle_enable, name='vehicle_type_model_toggle_enable'),

    # Emission Standard Master
    path('emission-standard/', views.emission_standard_list, name='emission_standard_list'),
    path('emission-standard/create/', views.emission_standard_create, name='emission_standard_create'),
    path('emission-standard/edit/<uuid:id>/', views.emission_standard_edit, name='emission_standard_edit'),
    path('emission-standard/delete/<uuid:id>/', views.emission_standard_delete, name='emission_standard_delete'),

    # Scheme Type
    path('scheme-type/', views.scheme_type_list, name='scheme_type_list'),
    path('scheme-type/create/', views.scheme_type_create, name='scheme_type_create'),
    path('scheme-type/edit/<uuid:id>/', views.scheme_type_edit, name='scheme_type_edit'),
    path('scheme-type/delete/<uuid:id>/', views.scheme_type_delete, name='scheme_type_delete'),
    
    # Expense Head
    path('expense-head/', views.expense_head_list, name='expense_head_list'),
    path('expense-head/create/', views.expense_head_create, name='expense_head_create'),
    path('expense-head/edit/<uuid:id>/', views.expense_head_edit, name='expense_head_edit'),
    path('expense-head/delete/<uuid:id>/', views.expense_head_delete, name='expense_head_delete'),

    # Expense Item
    path('expense-item/', views.expense_item_list, name='expense_item_list'),
    path('expense-item/create/', views.expense_item_create, name='expense_item_create'),
    path('expense-item/edit/<uuid:id>/', views.expense_item_edit, name='expense_item_edit'),
    path('expense-item/delete/<uuid:id>/', views.expense_item_delete, name='expense_item_delete'),
    
    #Expense
    path('expense/list/',views.expense_list,name='expense_list'),
    path('expense/create/',views.expense_create,name='expense_create'),
    path('expense/edit/<uuid:pk>/',views.expense_edit,name='expense_edit'),
    path('expense/delete/<uuid:pk>/',views.expense_delete,name='expense_delete'),

    # Vehicle Color
    path('vehicle-color/', views.vehicle_color_list, name='vehicle_color_list'),
    path('vehicle-color/create/', views.vehicle_color_create, name='vehicle_color_create'),
    path('vehicle-color/edit/<uuid:id>/', views.vehicle_color_edit, name='vehicle_color_edit'),
    path('vehicle-color/delete/<uuid:id>/', views.vehicle_color_delete, name='vehicle_color_delete'),

    # Vehicle Brand/Model
    path('vehicle-brand-model/', views.vehicle_brand_model_list, name='vehicle_brand_model_list'),
    path('vehicle-brand-model/create/', views.vehicle_brand_model_create, name='vehicle_brand_model_create'),
    path('vehicle-brand-model/edit/<uuid:id>/', views.vehicle_brand_model_edit, name='vehicle_brand_model_edit'),
    path('vehicle-brand-model/delete/<uuid:id>/', views.vehicle_brand_model_delete, name='vehicle_brand_model_delete'),

    # Vehicle Make (Manufacturer)
    path('vehicle-make/', views.vehicle_make_list, name='vehicle_make_list'),
    path('vehicle-make/create/', views.vehicle_make_create, name='vehicle_make_create'),
    path('vehicle-make/edit/<uuid:id>/', views.vehicle_make_edit, name='vehicle_make_edit'),
    path('vehicle-make/delete/<uuid:id>/', views.vehicle_make_delete, name='vehicle_make_delete'),

    # Supplier Management
    path('supplier/', views.supplier_list, name='supplier_list'),
    path('supplier/create/', views.supplier_create, name='supplier_create'),
    path('supplier/edit/<uuid:id>/', views.supplier_edit, name='supplier_edit'),
    path('supplier/delete/<uuid:id>/', views.supplier_delete, name='supplier_delete'),

    # Oil Brand CRUD
    path('oil-brand/', views.oil_brand_list, name='oil_brand_list'),
    path('oil-brand/create/', views.oil_brand_create, name='oil_brand_create'),
    path('oil-brand/edit/<uuid:id>/', views.oil_brand_edit, name='oil_brand_edit'),
    path('oil-brand/delete/<uuid:id>/', views.oil_brand_delete, name='oil_brand_delete'),

    # Oil Filter Brand CRUD
    path('oil-filter-brand/', views.oil_filter_brand_list, name='oil_filter_brand_list'),
    path('oil-filter-brand/create/', views.oil_filter_brand_create, name='oil_filter_brand_create'),
    path('oil-filter-brand/edit/<uuid:id>/', views.oil_filter_brand_edit, name='oil_filter_brand_edit'),
    path('oil-filter-brand/delete/<uuid:id>/', views.oil_filter_brand_delete, name='oil_filter_brand_delete'),

    # Oil Filter CRUD
    path('oil-filter/', views.oil_filter_list, name='oil_filter_list'),
    path('oil-filter/create/', views.oil_filter_create, name='oil_filter_create'),
    path('oil-filter/edit/<uuid:id>/', views.oil_filter_edit, name='oil_filter_edit'),
    path('oil-filter/delete/<uuid:id>/', views.oil_filter_delete, name='oil_filter_delete'),

    # Oil Grade CRUD
    path('oil-grade/', views.oil_grade_list, name='oil_grade_list'),
    path('oil-grade/create/', views.oil_grade_create, name='oil_grade_create'),
    path('oil-grade/edit/<uuid:id>/', views.oil_grade_edit, name='oil_grade_edit'),
    path('oil-grade/delete/<uuid:id>/', views.oil_grade_delete, name='oil_grade_delete'),

    # Oil Product CRUD
    path('oil-product/', views.oil_product_list, name='oil_product_list'),
    path('oil-product/create/', views.oil_product_create, name='oil_product_create'),
    path('oil-product/edit/<uuid:id>/', views.oil_product_edit, name='oil_product_edit'),
    path('oil-product/delete/<uuid:id>/', views.oil_product_delete, name='oil_product_delete'),

    # Tyre Brand CRUD
    path('tyre-brand/', views.tyre_brand_list, name='tyre_brand_list'),
    path('tyre-brand/create/', views.tyre_brand_create, name='tyre_brand_create'),
    path('tyre-brand/edit/<uuid:id>/', views.tyre_brand_edit, name='tyre_brand_edit'),
    path('tyre-brand/delete/<uuid:id>/', views.tyre_brand_delete, name='tyre_brand_delete'),

    # Tyre Product CRUD
    path('tyre/', views.tyre_list, name='tyre_list'),
    path('tyre/create/', views.tyre_create, name='tyre_create'),
    path('tyre/edit/<uuid:id>/', views.tyre_edit, name='tyre_edit'),
    path('tyre/delete/<uuid:id>/', views.tyre_delete, name='tyre_delete'),

    # Oil Product Pricing CRUD
    path('oil-product-price/', views.oil_product_price_list, name='oil_product_price_list'),
    path('oil-product-price/create/', views.oil_product_price_create, name='oil_product_price_create'),
    path('oil-product-price/edit/<uuid:id>/', views.oil_product_price_edit, name='oil_product_price_edit'),
    path('oil-product-price/delete/<uuid:id>/', views.oil_product_price_delete, name='oil_product_price_delete'),

    # Battery Make CRUD
    path('battery-make/', views.battery_make_list, name='battery_make_list'),
    path('battery-make/create/', views.battery_make_create, name='battery_make_create'),
    path('battery-make/edit/<uuid:id>/', views.battery_make_edit, name='battery_make_edit'),
    path('battery-make/delete/<uuid:id>/', views.battery_make_delete, name='battery_make_delete'),

    # Battery Ampere CRUD
    path('battery-ampere/', views.battery_ampere_list, name='battery_ampere_list'),
    path('battery-ampere/create/', views.battery_ampere_create, name='battery_ampere_create'),
    path('battery-ampere/edit/<uuid:id>/', views.battery_ampere_edit, name='battery_ampere_edit'),
    path('battery-ampere/delete/<uuid:id>/', views.battery_ampere_delete, name='battery_ampere_delete'),

    # Battery Segment CRUD
    path('battery-segment/', views.battery_segment_list, name='battery_segment_list'),
    path('battery-segment/create/', views.battery_segment_create, name='battery_segment_create'),
    path('battery-segment/edit/<uuid:id>/', views.battery_segment_edit, name='battery_segment_edit'),
    path('battery-segment/delete/<uuid:id>/', views.battery_segment_delete, name='battery_segment_delete'),

    # Battery Management CRUD
    path('battery/', views.battery_list, name='battery_list'),
    path('battery/create/', views.battery_create, name='battery_create'),
    path('battery/edit/<uuid:id>/', views.battery_edit, name='battery_edit'),
    path('battery/delete/<uuid:id>/', views.battery_delete, name='battery_delete'),

    # Stock Group & Sub-Group CRUD
    path('stock-group/', views.stock_group_list, name='stock_group_list'),
    path('stock-group/create/', views.stock_group_create, name='stock_group_create'),
    path('stock-group/edit/<uuid:id>/', views.stock_group_edit, name='stock_group_edit'),
    path('stock-group/delete/<uuid:id>/', views.stock_group_delete, name='stock_group_delete'),

    path('stock-subgroup/', views.stock_subgroup_list, name='stock_subgroup_list'),
    path('stock-subgroup/create/', views.stock_subgroup_create, name='stock_subgroup_create'),
    path('stock-subgroup/edit/<uuid:id>/', views.stock_subgroup_edit, name='stock_subgroup_edit'),
    path('stock-subgroup/delete/<uuid:id>/', views.stock_subgroup_delete, name='stock_subgroup_delete'),

    # Purchase Invoice CRUD & ERP Purchase System
    path('purchase-invoice/', views.purchase_invoice_list, name='purchase_invoice_list'),
    path('purchase-invoice/create/', views.purchase_invoice_create, name='purchase_invoice_create'),
    path('purchase-invoice/detail/<uuid:id>/', views.purchase_invoice_detail, name='purchase_invoice_detail'),

    # Supplier Payables & Payments
    path('supplier-payables/', views.supplier_payables_list, name='supplier_payables_list'),
    path('supplier-payables/pay/<uuid:supplier_id>/', views.supplier_payment_create, name='supplier_payment_create'),
]

