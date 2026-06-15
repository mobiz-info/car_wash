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
    api_password = "Mobiz123@"
    sender = "9496007007"
    
    if setting:
        base_url = setting.url or base_url
        username = setting.username or username
        api_password = setting.password or api_password
        sender = setting.whatsapp_number or sender

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
    Public-facing WhatsApp Cloud API Webhook.
    Handles verification (GET) and incoming message routing (POST).
    """
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Verify token must match what is configured in the Meta Developer Console
        VERIFY_TOKEN = 'mobiz_carwash_verify_token'
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse('Unauthorized', status=401)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            
            if 'messages' in value:
                message = value['messages'][0]
                from_phone = message.get('from', '')
                
                # Check for receiver business details in metadata
                recipient_metadata = value.get('metadata', {})
                business_phone = recipient_metadata.get('display_phone_number', '')
                phone_id = recipient_metadata.get('phone_number_id', '')
                
                # Retrieve the company's WhatsAppSetting configuration
                setting = None
                if phone_id:
                    setting = WhatsAppSetting.objects.filter(sender_id=phone_id).first()
                if not setting and business_phone:
                    # Suffix match on business phone setting to handle country prefixes flexibly
                    setting = WhatsAppSetting.objects.filter(whatsapp_number__icontains=business_phone[-10:]).first()
                if not setting:
                    # Fallback to the first available WhatsAppSetting in the system if metadata lookup failed
                    setting = WhatsAppSetting.objects.filter(is_deleted=False).first()
                
                if setting:
                    company = setting.company
                    
                    # 1. Search for customer by phone suffix (last 10 digits)
                    phone_suffix = from_phone[-10:] if len(from_phone) >= 10 else from_phone
                    customer = Customer.objects.filter(
                        Q(phone__endswith=phone_suffix) | Q(whatsapp_number__endswith=phone_suffix),
                        company=company,
                        is_deleted=False
                    ).select_related('branch').first()
                    
                    # 2. Determine reply and branches fallback
                    if customer:
                        branch_name = customer.branch.name if customer.branch else "our branch"
                        reply_text = f"Dear {customer.name}, Thank you for choosing {branch_name}."
                    else:
                        first_branch = company.branches.filter(is_deleted=False).first()
                        branch_name = first_branch.name if first_branch else company.company_name
                        reply_text = f"Thank you for contacting {branch_name}."
                    
                    # 3. Post reply to Webgenie API
                    response_text = send_whatsapp_simple(from_phone, reply_text, setting=setting)
                    status_str = 'Sent' if 'success' in response_text.lower() or 'wa_' in response_text.lower() else 'Failed'
                    
                    # 4. Log the message in WhatsAppMessage
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
            
        return JsonResponse({'status': 'success'})

