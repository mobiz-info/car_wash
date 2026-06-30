from django.urls import path
from . import views, api_views

urlpatterns = [
    path('bookings/', views.booking_list, name='booking_list'),
    path('api/booking/create/', api_views.api_create_booking, name='api_create_booking'),
    path('api/booking/list/', api_views.api_list_bookings, name='api_list_bookings'),
    path('api/booking/<uuid:booking_id>/status/', api_views.api_update_booking_status, name='api_update_booking_status'),
    path('api/booking/<uuid:booking_id>/ready-alert/', api_views.api_send_ready_alert, name='api_send_ready_alert'),
    path('api/booking/ready-alert/generic/', api_views.api_send_ready_alert_generic, name='api_send_ready_alert_generic'),
    path('api/whatsapp/webhook/', api_views.api_whatsapp_webhook, name='api_whatsapp_webhook'),
    path('api/whatsapp/webhook', api_views.api_whatsapp_webhook),
    path('api/whatsapp/debug/', api_views.api_whatsapp_debug, name='api_whatsapp_debug'),
    path('api/whatsapp/debug', api_views.api_whatsapp_debug),

    # Booking Settings API
    path('api/booking/settings/', api_views.api_get_booking_settings, name='api_get_booking_settings'),
    path('api/booking/settings/update/', api_views.api_update_booking_settings, name='api_update_booking_settings'),
    
    # Holiday Calendar API
    path('api/booking/holiday/list/', api_views.api_holiday_list, name='api_holiday_list'),
    path('api/booking/holiday/create/', api_views.api_holiday_create, name='api_holiday_create'),
    path('api/booking/holiday/delete/', api_views.api_holiday_delete, name='api_holiday_delete'),
    
    # Weekly Off Days API
    path('api/booking/weekly-off/list/', api_views.api_weekly_off_list, name='api_weekly_off_list'),
    path('api/booking/weekly-off/create/', api_views.api_weekly_off_create, name='api_weekly_off_create'),
    path('api/booking/weekly-off/delete/', api_views.api_weekly_off_delete, name='api_weekly_off_delete'),
    
    # Booking Pause API
    path('api/booking/pause/list/', api_views.api_booking_pause_list, name='api_booking_pause_list'),
    path('api/booking/pause/create/', api_views.api_booking_pause_create, name='api_booking_pause_create'),
    path('api/booking/pause/delete/', api_views.api_booking_pause_delete, name='api_booking_pause_delete'),
    
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
