from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(District)
admin.site.register(State)
admin.site.register(ExpenseHead)
admin.site.register(Expense)
admin.site.register(ExpenseEntry)