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
]

