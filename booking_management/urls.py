from django.urls import path
from . import views, api_views

urlpatterns = [
    path('bookings/', views.booking_list, name='booking_list'),
    path('api/booking/create/', api_views.api_create_booking, name='api_create_booking'),
    path('api/booking/list/', api_views.api_list_bookings, name='api_list_bookings'),
    path('api/booking/<uuid:booking_id>/status/', api_views.api_update_booking_status, name='api_update_booking_status'),
    path('api/whatsapp/webhook/', api_views.api_whatsapp_webhook, name='api_whatsapp_webhook'),
    
    path('holiday-calendar/', views.holiday_calendar, name='holiday_calendar'),
    path('holiday-calendar/create/', views.holiday_create, name='holiday_create'),
    path('holiday-calendar/delete/<uuid:id>/', views.holiday_delete, name='holiday_delete'),

    path('weekly-off/',views.weekly_off_list,name='weekly_off_list'),
    path('weekly-off/create/',views.weekly_off_create,name='weekly_off_create'),
    path('weekly-off/delete/<uuid:id>/',views.weekly_off_delete,name='weekly_off_delete'),

    path('booking-settings/',views.booking_settings,name='booking_settings'),
    
    path('pause-booking/',views.pause_booking_list,name='pause_booking_list'),
    path('pause-booking/create/',views.pause_booking_create,name='pause_booking_create'),
    path('pause-booking/delete/<uuid:pk>/',views.pause_booking_delete,name='pause_booking_delete'),
]
