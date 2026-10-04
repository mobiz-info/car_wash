from django.contrib import admin
from .models import Invoice, InvoiceItem, Receipt

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    fields = ('service_name', 'qty', 'rate', 'discount', 'net_taxable_amount', 'is_operational', 'remarks')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'customer',
        'vehicle',
        'branch',
        'invoice_type',
        'total',
        'amount_collected',
        'date',
    )
    search_fields = (
        'invoice_number',
        'customer__name',
        'customer__phone',
        'vehicle__vehicle_number',
        'remarks',
    )
    list_filter = (
        'invoice_type',
        'branch',
        'date',
    )
    date_hierarchy = 'date'
    ordering = ('-date', '-auto_id')
    inlines = [InvoiceItemInline]

@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'service_name', 'qty', 'rate', 'discount', 'net_taxable_amount', 'is_operational')
    search_fields = ('invoice__invoice_number', 'service_name', 'invoice__customer__name')
    list_filter = ('is_operational',)