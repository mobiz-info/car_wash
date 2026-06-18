import json
from urllib.parse import urlencode
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime
from .utils import validate_booking
from django.db.models import Q
from client_management.api_views import get_user_from_token
from client_management.models import Customer, CustomerVehicle, Scheme, WhatsAppSetting, WhatsAppMessage
from finance_management.models import Invoice
from .models import Booking


@csrf_exempt
def api_create_booking(request):
    """Create a booking for a vehicle."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        vehicle_id = data.get('vehicle_id')
        booking_date = data.get('booking_date')  # 'YYYY-MM-DD'

        if not customer_id or not vehicle_id or not booking_date:
            return JsonResponse({'success': False, 'message': 'customer_id, vehicle_id and booking_date are required'}, status=400)

        customer = Customer.objects.get(id=customer_id, is_deleted=False)
        vehicle = CustomerVehicle.objects.get(id=vehicle_id, customer=customer, is_deleted=False)
        booking_date_obj = datetime.strptime(
            booking_date,
            "%Y-%m-%d"
        ).date()

        is_valid, message = validate_booking(
            customer.branch,
            booking_date_obj
        )

        if not is_valid:
            return JsonResponse({
                'success': False,
                'message': message
            }, status=400)
        from core.functions import get_auto_id
        booking = Booking.objects.create(
            customer=customer,
            vehicle=vehicle,
            branch=customer.branch,
            booking_date=booking_date_obj,
            booking_time=data.get('booking_time') or None,
            notes=data.get('notes', ''),
            creator=user,
            auto_id=get_auto_id(Booking),
        )

        return JsonResponse({
            'success': True,
            'message': 'Booking created successfully',
            'booking_id': str(booking.id),
            'booking_date': str(booking.booking_date),
            'status': booking.status,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def api_list_bookings(request):
    """List bookings for the branch with optional date filters."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    bookings = Booking.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).order_by('booking_date', 'booking_time')

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        bookings = bookings.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        bookings = bookings.filter(branch__company=user.profile.company)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    if from_date:
        bookings = bookings.filter(booking_date__gte=from_date)
    if to_date:
        bookings = bookings.filter(booking_date__lte=to_date)

    results = []
    for b in bookings:
        results.append({
            'id': str(b.id),
            'booking_date': str(b.booking_date),
            'booking_time': str(b.booking_time) if b.booking_time else None,
            'status': b.status,
            'notes': b.notes or '',
            'customer': {
                'id': str(b.customer.id),
                'name': b.customer.name,
                'phone': b.customer.phone,
                'type': b.customer.customer_type.name if b.customer.customer_type else '',
            },
            'vehicle': {
                'id': str(b.vehicle.id),
                'number': b.vehicle.vehicle_number,
                'model': b.vehicle.vehicle_type_model.name if b.vehicle.vehicle_type_model else '',
                'no': b.vehicle.vehicle_number,
                'type': b.vehicle.vehicle_type_model.name if b.vehicle.vehicle_type_model else '',
            },
            'branch': b.branch.name if b.branch else '',
        })

    return JsonResponse({'success': True, 'bookings': results})


@csrf_exempt
def api_update_booking_status(request, booking_id):
    """Update the status of a booking (start → confirmed, cancel → cancelled)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        booking = Booking.objects.get(id=booking_id, is_deleted=False)
        data = json.loads(request.body)
        new_status = data.get('status')
        if new_status not in ['confirmed', 'cancelled', 'completed', 'pending']:
            return JsonResponse({'success': False, 'message': 'Invalid status'}, status=400)
        booking.status = new_status
        booking.save()
        return JsonResponse({'success': True, 'message': 'Status updated', 'status': booking.status})
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Booking not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def send_whatsapp_simple(to_number, message, setting=None, interactive_data=None):
    base_url = "http://wawy.org/conv_wa.php"
    username = "mobiz"
    api_password = "e36981wr6npxjbv7f"
    sender = "919496007007"

    if setting:
        if setting.url:
            base_url = setting.url
        if setting.username:
            username = setting.username
        if setting.password:
            api_password = setting.password
        if setting.sender_id:
            sender = setting.sender_id

    # If it is interactive
    if interactive_data:
        # Construct the JSON payload
        import json
        # Determine interactive_type: 1 for List, 2 for Button
        interactive_type = "1"
        if "buttons" in interactive_data:
            interactive_type = "2"

        payload = {
            "username": username,
            "api_password": api_password,
            "sender": sender,
            "interactive_type": interactive_type,
            "data": [
                {
                    "number": to_number,
                    "message": message,
                    "header_message": "Choose service",
                    "footer_message": "",
                    "interactive": interactive_data
                }
            ]
        }
        
        # Send via POST request
        from urllib.request import Request, urlopen
        from urllib.error import URLError
        
        try:
            req = Request(base_url, method='POST')
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            jsondata = json.dumps(payload).encode('utf-8')
            req.add_header('Content-Length', len(jsondata))
            
            with urlopen(req, jsondata, timeout=15) as resp:
                result = resp.read().decode('utf-8')
        except URLError as e:
            result = f"URLError: {str(e)}"
        except Exception as e:
            result = f"Exception: {str(e)}"
    else:
        # Standard GET message
        from urllib.request import urlopen
        from urllib.error import URLError
        
        params = {
            "username": username,
            "api_password": api_password,
            "sender": sender,
            "to": to_number,
            "message": message
        }
        try:
            url = f"{base_url}?{urlencode(params)}"
            with urlopen(url, timeout=15) as resp:
                result = resp.read().decode('utf-8')
        except URLError as e:
            result = f"URLError: {str(e)}"
        except Exception as e:
            result = f"Exception: {str(e)}"

    # Write debug log on server so we can check what happened
    try:
        log_path = '/tmp/whatsapp_webhook.log'
        with open(log_path, 'a') as f:
            from datetime import datetime
            f.write(f"[{datetime.now()}] to={to_number} result={result}\n")
    except Exception:
        pass

    return result


@csrf_exempt
def api_whatsapp_debug(request):
    """Debug endpoint — returns JSON showing exactly what the webhook would do.
    Hit: http://68.183.94.11:78/api/whatsapp/debug/?number=917510720297
    """
    test_number = request.GET.get('number', '917510720297').strip()
    test_msg = request.GET.get('msg', 'test').strip()

    # Read server log file
    log_contents = ''
    try:
        with open('/tmp/whatsapp_webhook.log', 'r') as f:
            lines = f.readlines()
            log_contents = ''.join(lines[-100:])  # last 100 lines
    except Exception as e:
        log_contents = f'Log not found: {e}'

    # Check settings in DB
    settings_info = []
    try:
        for s in WhatsAppSetting.objects.filter(is_deleted=False):
            settings_info.append({
                'company': s.company.company_name if s.company else None,
                'url': s.url,
                'username': s.username,
                'password_set': bool(s.password),
                'whatsapp_number': s.whatsapp_number,
                'sender_id': s.sender_id,
            })
    except Exception as e:
        settings_info = [f'Error: {e}']

    # Try sending a real message
    api_result = send_whatsapp_simple(test_number, f'Debug test to {test_number}')

    import os
    env_info = {k: v for k, v in os.environ.items() if 'PASS' not in k.upper() and 'SECRET' not in k.upper() and 'KEY' not in k.upper()}

    return JsonResponse({
        'test_number': test_number,
        'api_result': api_result,
        'settings_in_db': settings_info,
        'server_log_last_20_lines': log_contents,
        'request_meta': {
            'HTTP_HOST': request.META.get('HTTP_HOST'),
            'HTTP_X_FORWARDED_FOR': request.META.get('HTTP_X_FORWARDED_FOR'),
            'HTTP_X_FORWARDED_PROTO': request.META.get('HTTP_X_FORWARDED_PROTO'),
            'SERVER_PORT': request.META.get('SERVER_PORT'),
            'scheme': request.scheme,
        },
        'env_info': env_info,
    }, json_dumps_params={'indent': 2})


@csrf_exempt
def api_whatsapp_webhook(request):
    """
    Webgenie/wawy.org WhatsApp Chatbot Webhook.
    Webgenie sends incoming customer messages as a GET request with query parameters:
      ?number=#whats_number#&msg=#message#
    wawy.org passes the sender's WhatsApp number in 'number' and the URL-encoded message in 'msg'.
    """
    # Write a raw log of the request to debug connectivity
    try:
        with open('/tmp/whatsapp_webhook.log', 'a') as f:
            from datetime import datetime
            f.write(f"[{datetime.now()}] RAW REQUEST: method={request.method}, path={request.path}, GET={dict(request.GET)}, POST={dict(request.POST)}, body={request.body[:500]}\n")
    except Exception:
        pass

    # wawy.org sends incoming message as GET with query params: ?number=...&msg=...
    if request.method in ('GET', 'POST'):
        # --- Read incoming parameters (works for both GET and POST) ---
        choice_id = ''
        if request.method == 'GET':
            from_phone   = request.GET.get('number', '').strip()
            incoming_msg = request.GET.get('msg', '').strip()
            choice_id    = request.GET.get('id', '').strip() or request.GET.get('button_id', '').strip()
        else:
            # Some providers send as form POST
            try:
                body = json.loads(request.body)
                from_phone   = body.get('number', '').strip()
                incoming_msg = body.get('msg', '').strip()
                choice_id    = body.get('id', '').strip() or body.get('button_id', '').strip()
            except Exception:
                from_phone   = request.POST.get('number', '').strip()
                incoming_msg = request.POST.get('msg', '').strip()
                choice_id    = request.POST.get('id', '').strip() or request.POST.get('button_id', '').strip()

        if not from_phone:
            return HttpResponse('OK', status=200)

        # Log incoming request
        try:
            with open('/tmp/whatsapp_webhook.log', 'a') as f:
                from datetime import datetime
                f.write(f"[{datetime.now()}] INCOMING: from_phone={from_phone}, msg={incoming_msg}\n")
        except Exception:
            pass

        try:
            # 1. Resolve WhatsAppSetting
            # We support query parameters 'bot_number' or 'company_id' passed in the wawy.org webhook URL:
            # e.g., http://68.183.94.11:78/api/whatsapp/webhook/?number=#whats_number#&msg=#message#&bot_number=919496007007
            bot_number = request.GET.get('bot_number', '').strip() or request.POST.get('bot_number', '').strip()
            company_id = request.GET.get('company_id', '').strip() or request.POST.get('company_id', '').strip()

            setting = None
            if company_id:
                setting = WhatsAppSetting.objects.filter(company_id=company_id, is_deleted=False).first()

            if not setting and bot_number:
                bot_suffix = bot_number[-10:] if len(bot_number) >= 10 else bot_number
                setting = WhatsAppSetting.objects.filter(whatsapp_number__endswith=bot_suffix, is_deleted=False).first()

            # If not identified by parameters, try to identify by matching the incoming customer's phone number
            # to see which company they belong to.
            phone_suffix = from_phone[-10:] if len(from_phone) >= 10 else from_phone
            if not setting:
                customer = Customer.objects.filter(
                    Q(phone__endswith=phone_suffix) | Q(whatsapp_number__endswith=phone_suffix),
                    is_deleted=False
                ).select_related('company').first()
                if customer:
                    setting = WhatsAppSetting.objects.filter(company=customer.company, is_deleted=False).first()

            # Fallback to the first active WhatsAppSetting that has a username configured
            if not setting:
                setting = (
                    WhatsAppSetting.objects.filter(is_deleted=False).exclude(username__isnull=True).exclude(username='').first()
                    or WhatsAppSetting.objects.filter(is_deleted=False).first()
                )

            if not setting:
                return HttpResponse('OK', status=200)

            company = setting.company

            # 2. Search for customer by phone suffix (last 10 digits)
            customer = Customer.objects.filter(
                Q(phone__endswith=phone_suffix) | Q(whatsapp_number__endswith=phone_suffix),
                company=company,
                is_deleted=False
            ).select_related('branch').first()

            # 3. Build reply text and check for interactive menu selections
            choice = (choice_id or '').lower().strip() or (incoming_msg or '').lower().strip()
            
            interactive_menu = None
            is_menu = True
            
            # Resolve branch
            branch = None
            if customer:
                branch = customer.branch
            if not branch:
                branch = company.branches.filter(is_deleted=False).first()

            from booking_management.models import BookingSettings, HolidayCalendar, WeeklyOffDay, BookingPause
            from datetime import timedelta
            
            if "scheme" in choice:
                reply_text = "Here are our active schemes. Please reply or contact us for more details."
                is_menu = False
            elif choice == "menu_book" or (choice == "book" and not choice.startswith("book_date_") and not choice.startswith("book_veh_")):
                if not customer:
                    reply_text = "Please register as a customer first to use our booking services."
                    is_menu = False
                elif not branch:
                    reply_text = "Sorry, no active branch is associated with your account."
                    is_menu = False
                else:
                    # Check if booking is enabled
                    booking_setting = BookingSettings.objects.filter(branch=branch).first()
                    if booking_setting and not booking_setting.is_booking_enabled:
                        reply_text = "Sorry, bookings are currently disabled for this branch."
                        is_menu = False
                    else:
                        reply_text = "Bookings are open! Please select the booking date below:"
                        interactive_menu = {
                            "buttons": [
                                { "title": "Today", "button_id": "book_date_today" },
                                { "title": "Tomorrow", "button_id": "book_date_tomorrow" }
                            ]
                        }
            elif choice == "book_date_today" or choice == "today":
                if not customer or not branch:
                    reply_text = "Please register as a customer first to use our booking services."
                    is_menu = False
                else:
                    booking_date = timezone.localdate()
                    # Check holiday
                    holiday_exists = HolidayCalendar.objects.filter(branch=branch, holiday_date=booking_date).exists()
                    weekday = booking_date.strftime("%A").lower()
                    weekly_off = WeeklyOffDay.objects.filter(branch=branch, day=weekday).exists()
                    
                    if holiday_exists or weekly_off:
                        reply_text = "Sorry, today is a holiday / weekly off. Bookings are closed."
                        is_menu = False
                    else:
                        # Check paused
                        pause_exists = BookingPause.objects.filter(
                            branch=branch,
                            from_date__lte=booking_date,
                            to_date__gte=booking_date
                        ).exists()
                        if pause_exists:
                            reply_text = "Sorry, booking is paused for today."
                            is_menu = False
                        else:
                            # Show vehicles
                            vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                            if not vehicles.exists():
                                reply_text = "No registered vehicles found. Please add a vehicle to your account first."
                                is_menu = False
                            else:
                                reply_text = "Choose a vehicle to book for Today:"
                                choices_list = []
                                for v in vehicles:
                                    model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                    choices_list.append({
                                        "title": v.vehicle_number[:20], # limit to 20 chars
                                        "choice_id": f"book_veh_{v.id}_today",
                                        "description": model_name[:72] # limit to 72 chars
                                    })
                                interactive_menu = {
                                    "list_title": "Choose Vehicle",
                                    "sections": [
                                        {
                                            "title": "Your Vehicles",
                                            "choices": choices_list
                                        }
                                    ]
                                }
            elif choice == "book_date_tomorrow" or choice == "tomorrow":
                if not customer or not branch:
                    reply_text = "Please register as a customer first to use our booking services."
                    is_menu = False
                else:
                    booking_date = timezone.localdate() + timedelta(days=1)
                    # Check holiday
                    holiday_exists = HolidayCalendar.objects.filter(branch=branch, holiday_date=booking_date).exists()
                    weekday = booking_date.strftime("%A").lower()
                    weekly_off = WeeklyOffDay.objects.filter(branch=branch, day=weekday).exists()
                    
                    if holiday_exists or weekly_off:
                        reply_text = "Sorry, tomorrow is a holiday / weekly off. Bookings are closed."
                        is_menu = False
                    else:
                        # Check paused
                        pause_exists = BookingPause.objects.filter(
                            branch=branch,
                            from_date__lte=booking_date,
                            to_date__gte=booking_date
                        ).exists()
                        if pause_exists:
                            reply_text = "Sorry, booking is paused for tomorrow."
                            is_menu = False
                        else:
                            # Show vehicles
                            vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                            if not vehicles.exists():
                                reply_text = "No registered vehicles found. Please add a vehicle to your account first."
                                is_menu = False
                            else:
                                reply_text = "Choose a vehicle to book for Tomorrow:"
                                choices_list = []
                                for v in vehicles:
                                    model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                    choices_list.append({
                                        "title": v.vehicle_number[:20],
                                        "choice_id": f"book_veh_{v.id}_tomorrow",
                                        "description": model_name[:72]
                                    })
                                interactive_menu = {
                                    "list_title": "Choose Vehicle",
                                    "sections": [
                                        {
                                            "title": "Your Vehicles",
                                            "choices": choices_list
                                        }
                                    ]
                                }
            elif choice.startswith("book_veh_"):
                if not customer:
                    reply_text = "Please register as a customer first to use our booking services."
                    is_menu = False
                else:
                    parts = choice.split("_")
                    vehicle_id = parts[2]
                    day_str = parts[3]
                    
                    booking_date = timezone.localdate()
                    if day_str == "tomorrow":
                        booking_date += timedelta(days=1)
                    
                    try:
                        vehicle = CustomerVehicle.objects.get(id=vehicle_id, customer=customer)
                        
                        # Validate booking availability
                        from .utils import validate_booking
                        is_valid, validation_msg = validate_booking(branch, booking_date)
                        if not is_valid:
                            reply_text = f"Sorry, booking is not available for this date: {validation_msg}."
                        else:
                            # Create the booking record
                            from core.functions import get_auto_id
                            booking = Booking.objects.create(
                                customer=customer,
                                vehicle=vehicle,
                                branch=branch,
                                booking_date=booking_date,
                                status=Booking.STATUS_PENDING,
                                auto_id=get_auto_id(Booking)
                            )
                            reply_text = f"Booking confirmed! Your appointment for {vehicle.vehicle_number} has been scheduled for {booking_date.strftime('%d-%b-%Y')} ({day_str.capitalize()})."
                    except Exception as e:
                        reply_text = f"Sorry, there was an error processing your booking: {e}"
                    
                    is_menu = False
            elif "cancel" in choice:
                reply_text = "To cancel your booking, please contact our support team."
                is_menu = False
            elif "status" in choice:
                reply_text = "To check your vehicle's work status, please reply with your vehicle number."
                is_menu = False
            elif "feedback" in choice:
                reply_text = "Thank you for your feedback! Please reply with your comments."
                is_menu = False
            elif "complaint" in choice:
                reply_text = "Please describe your complaint, and our manager will contact you shortly."
                is_menu = False
            elif "location" in choice or "map" in choice:
                reply_text = "Here is our location: https://maps.google.com/?q=Dirty+Bee+Auto+Hub"
                is_menu = False
            elif "call" in choice:
                reply_text = "You can call us directly at +919496007007."
                is_menu = False
            else:
                # Default greeting + main menu
                if customer:
                    branch_name = customer.branch.name if customer.branch else company.company_name
                    reply_text = f"Dear {customer.name}, Thank you for choosing {branch_name}."
                else:
                    first_branch = company.branches.filter(is_deleted=False).first()
                    branch_name = first_branch.name if first_branch else company.company_name
                    reply_text = f"Thank you for contacting {branch_name}."
                
                interactive_menu = {
                    "list_title": "Choose service",
                    "sections": [
                        {
                            "title": "Services",
                            "choices": [
                                { "title": "Schemes", "choice_id": "menu_schemes", "description": "View active schemes" },
                                { "title": "Book", "choice_id": "menu_book", "description": "Book a wash appointment" },
                                { "title": "Cancel booking", "choice_id": "menu_cancel", "description": "Cancel your booking" },
                                { "title": "Work Status", "choice_id": "menu_status", "description": "Check vehicle wash status" },
                                { "title": "Feedback", "choice_id": "menu_feedback", "description": "Share your experience" },
                                { "title": "Complaint", "choice_id": "menu_complaint", "description": "Raise a complaint" },
                                { "title": "Location Map", "choice_id": "menu_location", "description": "Find our branch" },
                                { "title": "Call Us", "choice_id": "menu_call", "description": "Contact support" }
                            ]
                        }
                    ]
                }

            # 4. Send reply via wawy.org/Webgenie API
            response_text = send_whatsapp_simple(from_phone, reply_text, setting=setting, interactive_data=interactive_menu)
            status_str = 'Sent' if ('success' in response_text.lower() or 'wa_' in response_text.lower()) else 'Failed'

            # 5. Log the outgoing message
            from core.functions import get_auto_id
            WhatsAppMessage.objects.create(
                company=company,
                recipient_number=from_phone,
                message=reply_text,
                status=status_str,
                auto_id=get_auto_id(WhatsAppMessage)
            )

            # Log outgoing reply
            try:
                with open('/tmp/whatsapp_webhook.log', 'a') as f:
                    from datetime import datetime
                    f.write(f"[{datetime.now()}] OUTGOING: to={from_phone}, reply={reply_text}, response={response_text}, status={status_str}\n")
            except Exception:
                pass

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            traceback.print_exc()
            # Write exception to log file
            try:
                with open('/tmp/whatsapp_webhook.log', 'a') as f:
                    from datetime import datetime
                    f.write(f"[{datetime.now()}] EXCEPTION from_phone={from_phone}: {tb}\n")
            except Exception:
                pass

    # Always return 200 so Webgenie does not retry
    return HttpResponse('OK', status=200)
