from django.contrib import admin
from .models import Customer, CustomerVehicle

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'date_added')
    search_fields = ('name', 'phone', 'email')
    ordering = ('-auto_id',)

@admin.register(CustomerVehicle)
class CustomerVehicleAdmin(admin.ModelAdmin):
    list_display = ('vehicle_number', 'customer', 'vehicle_type_model', 'fuel_type', 'date_added')
    search_fields = ('vehicle_number', 'customer__name', 'customer__phone')
    list_filter = ('fuel_type', 'wheel_type')
    ordering = ('-auto_id',)