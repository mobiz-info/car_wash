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


def send_whatsapp_simple(to_number, message, setting=None):
    base_url = "http://wawy.org/conv_wa.php"
    username = "mobiz"
    api_password = "e36981wr6npxjbv7f"
    sender = "919496007007"
    
    # if setting:
    #     base_url = setting.url or base_url
    #     username = setting.username or username
    #     api_password = setting.password or api_password
    #     sender = setting.whatsapp_number or sender

    params = {
        "username": username,
        "api_password": api_password,
        "sender": sender,
        "to": to_number,
        "message": message
    }
    
    import requests
    try:
        response = requests.get(f"{base_url}?{urlencode(params)}")
        if response.status_code == 200:
            return response.text
        return f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Exception: {str(e)}"


@csrf_exempt
def api_whatsapp_webhook(request):
    """
    Webgenie/wawy.org WhatsApp Chatbot Webhook.
    Webgenie sends incoming customer messages as a GET request with query parameters:
      ?number=#whats_number#&msg=#message#
    wawy.org passes the sender's WhatsApp number in 'number' and the URL-encoded message in 'msg'.
    """
    # wawy.org sends incoming message as GET with query params: ?number=...&msg=...
    if request.method in ('GET', 'POST'):
        # --- Read incoming parameters (works for both GET and POST) ---
        if request.method == 'GET':
            from_phone   = request.GET.get('number', '').strip()
            incoming_msg = request.GET.get('msg', '').strip()
        else:
            # Some providers send as form POST
            try:
                body = json.loads(request.body)
                from_phone   = body.get('number', '').strip()
                incoming_msg = body.get('msg', '').strip()
            except Exception:
                from_phone   = request.POST.get('number', '').strip()
                incoming_msg = request.POST.get('msg', '').strip()

        if not from_phone:
            return HttpResponse('OK', status=200)

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

            # 3. Build reply text
            if customer:
                branch_name = customer.branch.name if customer.branch else company.company_name
                reply_text = f"Dear {customer.name}, Thank you for choosing {branch_name}."
            else:
                first_branch = company.branches.filter(is_deleted=False).first()
                branch_name = first_branch.name if first_branch else company.company_name
                reply_text = f"Thank you for contacting {branch_name}."

            # 4. Send reply via wawy.org/Webgenie API
            response_text = send_whatsapp_simple(from_phone, reply_text, setting=setting)
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

        except Exception as e:
            import traceback
            traceback.print_exc()

    # Always return 200 so Webgenie does not retry
    return HttpResponse('OK', status=200)
