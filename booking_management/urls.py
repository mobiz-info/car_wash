from django.urls import path
from . import views, api_views

urlpatterns = [
    path('bookings/', views.booking_list, name='booking_list'),
    path('api/booking/create/', api_views.api_create_booking, name='api_create_booking'),
    path('api/booking/list/', api_views.api_list_bookings, name='api_list_bookings'),
    path('api/booking/<uuid:booking_id>/status/', api_views.api_update_booking_status, name='api_update_booking_status'),
]
