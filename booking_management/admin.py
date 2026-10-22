from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(BookingSettings)
admin.site.register(JobCard)
admin.site.register(JobCardServiceItem)
admin.site.register(JobCardPartItem)
admin.site.register(JobCardLabourItem)
admin.site.register(JobCardExtraItem)
