import json
from urllib.parse import urlencode
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta, date
from .utils import validate_booking
from django.db.models import Q
from django.db import transaction
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
        service_id = data.get('service_id')
        service_name = data.get('service_name')

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

        service_obj = None
        if service_id:
            from service_management.models import Service
            try:
                service_obj = Service.objects.get(id=service_id)
                if not service_name:
                    service_name = service_obj.name
            except Service.DoesNotExist:
                pass

        from core.functions import get_auto_id
        booking = Booking.objects.create(
            customer=customer,
            vehicle=vehicle,
            branch=customer.branch,
            service=service_obj,
            service_name=service_name or (service_obj.name if service_obj else ''),
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
    """List bookings for the branch with optional date and service filters."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    bookings = Booking.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch', 'service'
    ).order_by('booking_date', 'booking_time')

    role = user.profile.role.name if user.profile.role else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        bookings = bookings.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        bookings = bookings.filter(branch__company=user.profile.company)

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    service_id = request.GET.get('service_id')
    if from_date:
        bookings = bookings.filter(booking_date__gte=from_date)
    if to_date:
        bookings = bookings.filter(booking_date__lte=to_date)
    if service_id and service_id != 'all':
        bookings = bookings.filter(Q(service_id=service_id) | Q(service_name__icontains=service_id))

    results = []
    for b in bookings:
        results.append({
            'id': str(b.id),
            'booking_date': str(b.booking_date),
            'booking_time': str(b.booking_time) if b.booking_time else None,
            'status': b.status,
            'notes': b.notes or '',
            'service_name': b.service_name or (b.service.name if b.service else ''),
            'service_id': str(b.service.id) if b.service else None,
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
        
        # Trigger ready alert automatically if status is changed to completed
        if new_status == 'completed':
            import threading
            threading.Thread(
                target=send_booking_ready_alert_background,
                args=(str(booking.id),),
                daemon=True
            ).start()
            
        return JsonResponse({'success': True, 'message': 'Status updated', 'status': booking.status})
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Booking not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def safe_create_model(model, **kwargs):
    from django.db import IntegrityError
    from core.functions import get_auto_id
    import time
    
    for attempt in range(5):
        try:
            kwargs['auto_id'] = get_auto_id(model)
            return model.objects.create(**kwargs)
        except IntegrityError as e:
            if 'auto_id' in str(e).lower() or 'duplicate' in str(e).lower():
                time.sleep(0.1)  # Sleep 100ms and try again
                continue
            raise e
    kwargs['auto_id'] = get_auto_id(model)
    return model.objects.create(**kwargs)


def clean_whatsapp_number(number):
    """
    Cleans a phone number for WhatsApp sending.
    - Strips spaces, dashes, +, parentheses and other non-digit characters
    - Removes a single leading 0 (local dialing format)
    - Preserves existing international dial codes (Qatar 974, UAE 971, Saudi 966, Ghana 233, Ivory Coast 225, Benin 229, India 91, etc.)
    - Returns the cleaned digit string or None if too short to be valid
    """
    if not number:
        return None
    # Remove all non-digit characters (including the leading +)
    digits = ''.join(filter(str.isdigit, str(number).strip()))
    if not digits:
        return None
    # Strip a single leading 0 (local dialing prefix used in some countries)
    if digits.startswith('0') and len(digits) > 7:
        digits = digits[1:]

    # Check if number already starts with known international dial codes
    known_dial_codes = [
        '974', # Qatar
        '971', # UAE
        '966', # Saudi Arabia
        '965', # Kuwait
        '968', # Oman
        '973', # Bahrain
        '233', # Ghana
        '229', # Benin
        '225', # Ivory Coast
        '84',  # Vietnam
        '66',  # Thailand
        '7',   # Russia
        '86',  # China
        '1',   # USA / UK
        '44',  # UK
        '91',  # India
    ]

    has_country_code = False
    for code in known_dial_codes:
        if digits.startswith(code) and len(digits) > len(code) + 4:
            has_country_code = True
            break

    # Only default to 91 if no international country code is detected and it's a 10-digit number
    if not has_country_code and len(digits) == 10 and digits[0] in ('6', '7', '8', '9'):
        digits = '91' + digits

    # Reject obviously invalid numbers (anything shorter than 7 digits is not a real phone)
    if len(digits) < 7:
        return None
    return digits


def send_whatsapp_simple(to_number, message, setting=None, interactive_data=None, media_url=None, location_data=None):
    to_number = clean_whatsapp_number(to_number) or to_number

    # Each company must have its own WhatsAppSetting configured.
    # Never fall back to hardcoded credentials — that would mix one company's traffic into another's account.
    if not setting or not setting.username or not setting.password:
        with open('/tmp/wa_debug.log', 'a') as f:
            f.write(f"SEND_WA_SIMPLE ABORTED: no valid WhatsAppSetting provided\n")
        return "ABORTED: no WA setting"

    # Simple conversational text, interactive menus, location pins must ALWAYS use conv_wa.php
    base_url = "http://wawy.org/conv_wa.php"
    if setting and setting.url and 'conv_wa.php' in setting.url:
        base_url = setting.url
    username = setting.username
    api_password = setting.password
    sender = setting.sender_id or ""

    # If it is a location map pin
    if location_data:
        import json
        payload = {
            "username": username,
            "api_password": api_password,
            "sender": sender,
            "is_contact": "0",
            "data": [
                {
                    "number": to_number
                }
            ],
            "location": {
                "latitude": str(location_data.get("lat", "11.2588")),
                "longitude": str(location_data.get("lng", "75.7804")),
                "name": str(location_data.get("address", "")),
                "address": str(location_data.get("address", ""))
            }
        }
        from urllib.request import Request, urlopen
        from urllib.error import URLError
        
        try:
            req = Request(base_url, method='POST')
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            jsondata = json.dumps(payload).encode('utf-8')
            req.add_header('Content-Length', len(jsondata))
            
            with open('/tmp/wa_debug.log', 'a') as f:
                f.write(f"LOCATION PAYLOAD: {jsondata.decode()}\n")
            
            with urlopen(req, jsondata, timeout=15) as resp:
                result = resp.read().decode('utf-8')
                
            with open('/tmp/wa_debug.log', 'a') as f:
                f.write(f"LOCATION RESPONSE: {result}\n")
        except URLError as e:
            result = f"URLError: {str(e)}"
        except Exception as e:
            result = f"Exception: {str(e)}"

    # If it is interactive
    elif interactive_data:
        # Construct the JSON payload
        import json
        # Determine interactive_type: 1 for List, 2 for Button
        interactive_type = "1"
        if "buttons" in interactive_data:
            interactive_type = "2"

        # WhatsApp Gateway API limits list interactive menu to maximum 10 total choices across all sections
        if interactive_type == "1" and isinstance(interactive_data, dict):
            if "sections" in interactive_data and isinstance(interactive_data["sections"], list):
                total_count = 0
                max_allowed = 10
                new_sections = []
                for sec in interactive_data["sections"]:
                    if isinstance(sec, dict) and "choices" in sec:
                        rem = max_allowed - total_count
                        if rem <= 0:
                            break
                        choices = sec.get("choices", [])[:rem]
                        total_count += len(choices)
                        sec_copy = dict(sec)
                        sec_copy["choices"] = choices
                        new_sections.append(sec_copy)
                interactive_data["sections"] = new_sections

        header_msg = interactive_data.pop("header_message", "") if isinstance(interactive_data, dict) else ""
        footer_msg = interactive_data.pop("footer_message", "") if isinstance(interactive_data, dict) else ""

        payload = {
            "username": username,
            "api_password": api_password,
            "sender": sender,
            "interactive_type": interactive_type,
            "data": [
                {
                    "number": to_number,
                    "message": message,
                    "header_message": header_msg,
                    "footer_message": footer_msg,
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
            "message": message,
            "jsonapi": "1"
        }
        if media_url:
            params["media_url"] = media_url
            
        try:
            url = f"{base_url}?{urlencode(params)}"
            with open('/tmp/wa_debug.log', 'a') as f:
                f.write(f"GET URL: {url}\n")
            
            with urlopen(url, timeout=15) as resp:
                result = resp.read().decode('utf-8')
                
            with open('/tmp/wa_debug.log', 'a') as f:
                f.write(f"GET RESPONSE: {result}\n")
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


def send_whatsapp_template(to_number, template_name, values, doc_url=None, setting=None):
    """
    Sends an official WhatsApp template message via wawy.org pushwhatsapp.php.
    """
    import json
    from urllib.request import urlopen
    from urllib.parse import urlencode
    from urllib.error import URLError

    to_number = clean_whatsapp_number(to_number) or to_number

    # Each company must have its own WhatsAppSetting configured.
    # Never fall back to hardcoded credentials — that would mix companies.
    if not setting or not setting.username or not setting.password:
        try:
            with open('/tmp/wa_debug.log', 'a') as f:
                f.write(f"SEND_TEMPLATE ABORTED: no valid WhatsAppSetting provided\n")
        except Exception:
            pass
        return "ABORTED: no WA setting"

    username = setting.username
    api_password = setting.password
    sender = setting.sender_id or ""

    # Base URL for templates
    base_url = "http://wawy.org/pushwhatsapp.php"

    params = {
        "username": username,
        "api_password": api_password,
        "sender": sender,
        "priority": "21",
        "name": template_name,
        "to": to_number,
    }

    # Add dynamic values (value1, value2, value3...)
    for i, val in enumerate(values, start=1):
        params[f"value{i}"] = val

    if doc_url:
        params["doc"] = doc_url

    try:
        url = f"{base_url}?{urlencode(params)}"
        with open('/tmp/wa_debug.log', 'a') as f:
            f.write(f"SEND_TEMPLATE CALL: to={to_number}, template={template_name}, url={url}\n")
        
        with urlopen(url, timeout=15) as resp:
            result = resp.read().decode('utf-8')

        # Fallback between wheelalignment/wheelbalancing, welcome1/welcoming, thanks1/washinvoicemessage, and ready1/ready if template not found on Wawy portal
        if "Template or Sender Not Found" in result:
            alt_names = []
            tn_lower = template_name.lower()
            if tn_lower in ['alignmentinvoicemsg', 'wheelalignment', 'wheelbalancing']:
                alt_names = [n for n in ['alignmentinvoicemsg', 'wheelalignment', 'wheelbalancing'] if n != tn_lower]
            elif tn_lower in ['servicesreminder', 'reminderservice', 'servicereminder']:
                alt_names = [name for name in ['servicesreminder', 'reminderservice', 'servicereminder'] if name != tn_lower]
            elif tn_lower in ['welcome1', 'welcoming', 'welcome']:
                alt_names = [n for n in ['welcome1', 'welcoming', 'welcome'] if n != tn_lower]
            elif tn_lower in ['thanks1', 'washinvoicemessage', 'thanks', 'thankyou']:
                alt_names = [n for n in ['thanks1', 'washinvoicemessage', 'thanks', 'thankyou'] if n != tn_lower]
            elif tn_lower in ['ready1', 'ready']:
                alt_names = [n for n in ['ready1', 'ready'] if n != tn_lower]

            for alt_name in alt_names:
                alt_params = dict(params)
                alt_params["name"] = alt_name
                alt_url = f"{base_url}?{urlencode(alt_params)}"
                with open('/tmp/wa_debug.log', 'a') as f:
                    f.write(f"SEND_TEMPLATE FALLBACK RETRY: template={alt_name}, url={alt_url}\n")
                with urlopen(alt_url, timeout=15) as resp:
                    res_alt = resp.read().decode('utf-8')
                    if "Template or Sender Not Found" not in res_alt:
                        result = res_alt
                        break
            
        with open('/tmp/wa_debug.log', 'a') as f:
            f.write(f"SEND_TEMPLATE RESPONSE: {result}\n")
    except URLError as e:
        result = f"URLError: {str(e)}"
    except Exception as e:
        result = f"Exception: {str(e)}"

    # Write to standard logs
    try:
        log_path = '/tmp/whatsapp_webhook.log'
        with open(log_path, 'a') as f:
            from datetime import datetime
            f.write(f"[{datetime.now()}] TEMPLATE to={to_number} template={template_name} result={result}\n")
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
def api_invoice_wa_debug(request):
    """
    Read the invoice WhatsApp log and optionally test-send for a given invoice_id.
    GET  /api/whatsapp/invoice-log/            → show last 200 lines of log
    GET  /api/whatsapp/invoice-log/?invoice_id=<id>  → also trigger synchronous send
    """
    invoice_log = ''
    try:
        with open('/tmp/whatsapp_invoice.log', 'r') as f:
            lines = f.readlines()
            invoice_log = ''.join(lines[-200:])
    except Exception as e:
        invoice_log = f'Log not found or empty: {e}'

    wa_log = ''
    try:
        with open('/tmp/wa_debug.log', 'r') as f:
            lines = f.readlines()
            wa_log = ''.join(lines[-100:])
    except Exception as e:
        wa_log = f'wa_debug.log not found: {e}'

    result = {'invoice_log': invoice_log, 'wa_debug_log': wa_log}

    invoice_id = request.GET.get('invoice_id', '').strip()
    if invoice_id:
        try:
            from client_management.api_views import send_invoice_whatsapp_background
            base_url = request.build_absolute_uri('/')
            # Run SYNCHRONOUSLY (not in thread) for debugging
            send_invoice_whatsapp_background(invoice_id, base_url)
            # Re-read log after run
            try:
                with open('/tmp/whatsapp_invoice.log', 'r') as f:
                    lines = f.readlines()
                    result['invoice_log_after_test'] = ''.join(lines[-200:])
            except Exception as e:
                result['invoice_log_after_test'] = f'Could not re-read log: {e}'
            result['test_invoice_id'] = invoice_id
            result['test_status'] = 'send_invoice_whatsapp_background called synchronously'
        except Exception as e:
            import traceback
            result['test_error'] = f'{e}\n{traceback.format_exc()}'

    return JsonResponse(result, json_dumps_params={'indent': 2})


def get_local_date():
    from zoneinfo import ZoneInfo
    from django.utils import timezone
    return timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).date()


def _get_available_services(br, vehicle_match):
    """
    Return list of Service objects available for `br`.
    Guarantees active services are returned so WhatsApp bot can prompt for service selection.
    """
    from service_management.models import Service as ServiceModel, ServiceType, CompanyService, BranchService, BranchServiceCategory, ServiceVehicleTypePrice

    disabled_cat_slugs = set(
        BranchServiceCategory.objects.filter(
            branch=br, is_enabled=False, is_deleted=False
        ).values_list('service_type__slug', flat=True)
    )
    all_cat_slugs = list(
        ServiceType.objects.filter(is_deleted=False).values_list('slug', flat=True)
    )
    enabled_cat_slugs = [s for s in all_cat_slugs if s and s not in disabled_cat_slugs]

    qs = ServiceModel.objects.filter(
        is_active=True,
        is_deleted=False,
    )
    if enabled_cat_slugs:
        qs = qs.filter(service_type__slug__in=enabled_cat_slugs)

    company_svc_ids = set(CompanyService.objects.filter(
        company=br.company, is_enabled=True
    ).values_list('service_id', flat=True))

    branch_svc_ids = set(BranchService.objects.filter(
        branch=br,
        is_enabled=True,
        is_deleted=False
    ).values_list('service_id', flat=True))

    if company_svc_ids:
        qs = qs.filter(id__in=company_svc_ids)
    if branch_svc_ids:
        qs = qs.filter(id__in=branch_svc_ids)

    candidate_services = list(qs.order_by('service_type__name', 'name'))

    if not candidate_services:
        candidate_services = list(
            ServiceModel.objects.filter(
                is_active=True,
                is_deleted=False,
                service_type__slug__in=enabled_cat_slugs if enabled_cat_slugs else all_cat_slugs
            ).order_by('service_type__name', 'name')
        )

    if not candidate_services:
        candidate_services = list(
            ServiceModel.objects.filter(
                is_active=True,
                is_deleted=False
            ).order_by('service_type__name', 'name')
        )

    vehicle_type_model = vehicle_match.vehicle_type_model if vehicle_match else None
    available_services = []
    for svc in candidate_services:
        if vehicle_type_model:
            price_obj = ServiceVehicleTypePrice.objects.filter(
                branch=br,
                service=svc,
                vehicle_model=vehicle_type_model,
                is_active=True,
                is_deleted=False,
            ).first()
            if not price_obj:
                has_any_prices = ServiceVehicleTypePrice.objects.filter(
                    branch=br,
                    service=svc,
                    is_active=True,
                    is_deleted=False
                ).exists()
                if has_any_prices:
                    continue
        available_services.append(svc)

    if not available_services:
        available_services = candidate_services

    return available_services




def _build_service_choice(svc):
    desc = ""
    if svc.description and svc.description.strip() and svc.description.strip().lower() != svc.name.strip().lower():
        desc = svc.description.strip()[:72]
    elif svc.service_type and svc.service_type.name.strip().lower() != svc.name.strip().lower():
        desc = svc.service_type.name.strip()[:72]
    return {
        "title": svc.name[:24],
        "choice_id": f"book_svc_{svc.id}",
        "id": f"book_svc_{svc.id}",
        "button_id": f"book_svc_{svc.id}",
        "description": desc
    }


def _build_service_or_category_menu(br, vehicle_match, available_services):
    """
    If available_services count > 10, present Category (ServiceType) selection
    to respect WhatsApp's 10-item limit per interactive list.
    Otherwise, present the service list directly.
    """
    if not available_services:
        return None, None

    if len(available_services) > 10:
        cat_map = {}
        for svc in available_services:
            cat = svc.service_type
            if cat and cat.id not in cat_map:
                cat_map[cat.id] = cat

        cat_choices = []
        for cat_id, cat in cat_map.items():
            cat_choices.append({
                "title": cat.name[:24],
                "choice_id": f"book_cat_{cat.id}",
                "id": f"book_cat_{cat.id}",
                "button_id": f"book_cat_{cat.id}",
                "description": f"Browse {cat.name} services"[:72]
            })
            if len(cat_choices) >= 10:
                break

        reply_text = "Please select a service category below:"
        interactive_menu = {
            "header_message": "",
            "list_title": "Choose Category",
            "sections": [{"title": "Service Categories", "choices": cat_choices}]
        }
    else:
        choices_list = [_build_service_choice(svc) for svc in available_services]
        reply_text = "Please select the service you'd like to book:"
        interactive_menu = {
            "header_message": "",
            "list_title": "Choose Service",
            "sections": [{"title": "Available Services", "choices": choices_list[:10]}]
        }

    return reply_text, interactive_menu


def find_matching_branch(company, choice, choice_id_raw='', choice_title_raw='', incoming_msg=''):
    all_branches = company.branches.filter(is_deleted=False)

    if not all_branches.exists():
        return None
    if all_branches.count() == 1:
        return all_branches.first()

    candidates = []
    for raw in [choice_id_raw, choice_title_raw, choice, incoming_msg]:
        if not raw:
            continue
        cleaned = str(raw).strip()
        if cleaned:
            candidates.append(cleaned)
            for prefix in ['reg_br_', 'book_br_', 'sch_br_', 'contact_br_', 'loc_br_', 'br_']:
                if cleaned.lower().startswith(prefix):
                    candidates.append(cleaned[len(prefix):].strip())

    # 1. Match by UUID if candidate is valid UUID
    import uuid
    for cand in candidates:
        try:
            u = uuid.UUID(cand)
            br = all_branches.filter(id=u).first()
            if br:
                return br
        except Exception:
            pass

    # 2. Match by exact name (case-insensitive)
    for cand in candidates:
        br = all_branches.filter(name__iexact=cand).first()
        if br:
            return br

    # 3. Match by truncated prefix (WhatsApp may truncate title to any length)
    for cand in candidates:
        cand_lower = cand.lower().strip()
        if not cand_lower:
            continue
        for b in all_branches:
            b_lower = b.name.lower()
            # branch name starts with what we received (WhatsApp truncated it)
            if b_lower.startswith(cand_lower):
                return b
            # what we received starts with branch name (unlikely but safe)
            if cand_lower.startswith(b_lower):
                return b
            # match first 20 chars prefix
            if len(cand_lower) >= 10 and b_lower[:len(cand_lower)] == cand_lower:
                return b

    # 4. Match by substring overlap
    for cand in candidates:
        cand_lower = cand.lower()
        if len(cand_lower) >= 3:
            for b in all_branches:
                b_lower = b.name.lower()
                if cand_lower in b_lower or b_lower in cand_lower:
                    return b


    # 5. Match by word overlap
    for cand in candidates:
        cand_words = [w for w in cand.lower().split() if len(w) >= 3]
        if not cand_words:
            continue
        for b in all_branches:
            b_words = [w for w in b.name.lower().split() if len(w) >= 3]
            for cw in cand_words:
                if any(cw in bw or bw in cw for bw in b_words):
                    return b

    return None


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

    # wawy.org sends incoming message as GET/POST with query params or JSON body
    if request.method in ('GET', 'POST'):
        # --- Read incoming parameters (works for both GET and POST) ---
        choice_id = ''
        incoming_msg = ''
        from_phone = ''

        if request.method == 'GET':
            from_phone   = request.GET.get('number', '').strip()
            incoming_msg = (request.GET.get('msg', '').strip() or 
                            request.GET.get('message_in', '').strip() or 
                            request.GET.get('message', '').strip())
            choice_id    = (request.GET.get('id', '').strip() or 
                            request.GET.get('button_id', '').strip() or 
                            request.GET.get('choice_id', '').strip())
        else:
            # POST request
            try:
                body = json.loads(request.body)
                from_phone   = str(body.get('number', '')).strip()
                incoming_msg = str(body.get('message_in', '') or 
                                   body.get('msg', '') or 
                                   body.get('message', '')).strip()
                
                # Check interactive dict first (for wawy.org list/button selection)
                interactive_data = body.get('interactive') or {}
                interactive_type = str(interactive_data.get('type', '')).strip()
                choice_title = str(interactive_data.get('title', '') or body.get('title', '')).strip()
                # description field carries the full branch name we put in it
                choice_description = str(interactive_data.get('description', '') or '').strip()
                if choice_description and choice_description.lower() != 'none':
                    # Prefer description over truncated title for matching
                    choice_title = choice_description
                if interactive_type == '1':
                    # For list messages (type 1), wawy.org sends custom ID in 'id' and
                    # the selected item title in 'title'. Grab both.
                    choice_id = str(interactive_data.get('id', '')).strip()
                    if not choice_id:
                        choice_id = choice_title  # fallback to title if id is empty
                elif interactive_type == '2':
                    # For button messages (type 2), the custom button_id is preserved in 'btnid'.
                    choice_id = str(interactive_data.get('btnid', '') or interactive_data.get('id', '')).strip()
                else:
                    choice_id = str(
                        interactive_data.get('btnid', '') or 
                        interactive_data.get('id', '') or 
                        body.get('id', '') or 
                        body.get('button_id', '') or 
                        body.get('choice_id', '')
                    ).strip()
                    choice_title = choice_title or str(body.get('title', '')).strip()
            except Exception as e:
                # Log parsing error
                try:
                    with open('/tmp/whatsapp_webhook.log', 'a') as f:
                        from datetime import datetime
                        f.write(f"[{datetime.now()}] JSON PARSE ERROR: {str(e)}\n")
                except Exception:
                    pass
                # Form POST or fallback
                from_phone   = request.POST.get('number', '').strip()
                incoming_msg = (request.POST.get('message_in', '').strip() or 
                                request.POST.get('msg', '').strip() or 
                                request.POST.get('message', '').strip())
                choice_id    = (request.POST.get('btnid', '').strip() or
                                request.POST.get('id', '').strip() or 
                                request.POST.get('button_id', '').strip() or 
                                request.POST.get('choice_id', '').strip())

        if not from_phone:
            return HttpResponse('OK', status=200)

        # Decode URL-encoded parameters (like + or %20) from wawy.org
        from urllib.parse import unquote_plus
        choice_id = unquote_plus(choice_id)
        incoming_msg = unquote_plus(incoming_msg)
        # choice_title may not exist if this was a GET request
        try:
            choice_title = unquote_plus(choice_title)
        except NameError:
            choice_title = ''

        # Log incoming request
        try:
            with open('/tmp/whatsapp_webhook.log', 'a') as f:
                from datetime import datetime
                f.write(f"[{datetime.now()}] INCOMING: from_phone={from_phone}, msg={incoming_msg!r}, choice_id={choice_id!r}, choice_title={choice_title!r}\n")
        except Exception:
            pass

        try:
            # 1. Resolve WhatsAppSetting
            # We support query parameters 'bot_number' or 'company_id' passed in the webhook URL,
            # or sender_number / company_id inside JSON post body:
            json_bot_number = ""
            json_company_id = ""
            if request.method == 'POST':
                try:
                    post_body = json.loads(request.body)
                    json_bot_number = str(post_body.get('sender_number', '') or post_body.get('bot_number', '')).strip()
                    json_company_id = str(post_body.get('company_id', '')).strip()
                except Exception:
                    pass

            bot_number = (request.GET.get('bot_number', '').strip() or 
                          request.POST.get('bot_number', '').strip() or 
                          json_bot_number)
            company_id = (request.GET.get('company_id', '').strip() or 
                          request.POST.get('company_id', '').strip() or 
                          json_company_id)

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

            # If we cannot identify which company this reply belongs to, drop it safely.
            # Do NOT fall back to the first company — that would route another company's
            # customer through the wrong account.
            if not setting:
                with open('/tmp/whatsapp_webhook.log', 'a') as f:
                    from datetime import datetime
                    f.write(f"[{datetime.now()}] WEBHOOK ABORTED: cannot identify company for phone={from_phone}, bot_number={bot_number}, company_id={company_id}\n")
                return HttpResponse('OK', status=200)

            company = setting.company

            # 2. Search for customer by phone suffix (last 10 digits)
            customer = Customer.objects.filter(
                Q(phone__endswith=phone_suffix) | Q(whatsapp_number__endswith=phone_suffix),
                company=company,
                is_deleted=False
            ).select_related('branch').first()

            # 3. Build reply text and check for interactive menu selections
            from booking_management.models import ChatSession
            session = ChatSession.objects.filter(phone_number=from_phone, is_deleted=False).first()
            # 'choice' is the normalized identifier for matching state machine branches.
            # Priority: choice_id (our custom ID like 'reg_br_uuid') → choice_title (item display name) → incoming_msg
            choice = (
                (choice_id or '').lower().strip()
                or (choice_title or '').lower().strip()
                or (incoming_msg or '').lower().strip()
            )
            # Also keep the original-case title for name-based matching
            choice_title_raw = (choice_title or '').strip()
            choice_id_raw = (choice_id or '').strip()
            
            # Check if this is a vehicle selection (either via choice ID or via text title fallback)
            is_vehicle_selection = False
            vehicle_match = None
            day_str = ""
            
            if choice.startswith("book_veh_"):
                is_vehicle_selection = True
                parts = choice.split("_")
                vehicle_id = parts[2]
                day_str = parts[3]
                try:
                    vehicle_match = CustomerVehicle.objects.get(id=vehicle_id, customer=customer)
                except Exception:
                    pass
            elif customer:
                # Try matching via vehicle number in the message text
                cleaned_choice = choice.lower().strip()
                target_day = None
                veh_no_part = ""
                
                # Check for list selection text fallback
                if "choose a vehicle to book for" in cleaned_choice:
                    lines = [l.strip() for l in cleaned_choice.split("\n") if l.strip()]
                    if len(lines) >= 2:
                        header_line = lines[0]
                        if "tomorrow" in header_line:
                            target_day = "tomorrow"
                        elif "today" in header_line:
                            target_day = "today"
                        veh_no_part = lines[1]
                else:
                    if " today" in cleaned_choice:
                        target_day = "today"
                        veh_no_part = cleaned_choice.split(" today")[0].strip()
                    elif " tom" in cleaned_choice:
                        target_day = "tomorrow"
                        veh_no_part = cleaned_choice.split(" tom")[0].strip()
                    elif session and session.state == 'book_select_vehicle':
                        target_day = session.data.get('booking_date_str', 'today')
                        veh_no_part = cleaned_choice
                
                if target_day and veh_no_part:
                    # Look for a vehicle matching this number / description for this customer
                    best_match = None
                    best_match_len = 0
                    option_line_cleaned = ''.join(c for c in veh_no_part.lower() if c.isalnum())
                    for v in CustomerVehicle.objects.filter(customer=customer, is_deleted=False):
                        v_num_cleaned = ''.join(c for c in v.vehicle_number.lower() if c.isalnum())
                        if v_num_cleaned and v_num_cleaned in option_line_cleaned:
                            if len(v_num_cleaned) > best_match_len:
                                best_match = v
                                best_match_len = len(v_num_cleaned)
                    if best_match:
                        vehicle_match = best_match
                        is_vehicle_selection = True
                        day_str = target_day

            interactive_menu = None
            location_pin = None
            is_menu = True
            
            # Resolve branch
            branch = None
            if customer:
                branch = customer.branch
            if not branch:
                branch = company.branches.filter(is_deleted=False).first()

            from booking_management.models import BookingSettings, HolidayCalendar, WeeklyOffDay, BookingPause, ChatSession
            from datetime import timedelta
            if session and (choice.startswith("menu_") or choice in ["cancel", "abort", "reset", "hi", "hello", "hey", "menu"]):
                session.delete()
                session = None

            if session:
                interactive_menu = None
                is_menu = True
                
                if session.state == 'register_select_branch':
                    from client_management.models import Branch
                    br = find_matching_branch(company, choice, choice_id_raw, choice_title_raw, incoming_msg)

                    if br:
                        session.data['branch_id'] = str(br.id)
                        session.data['branch_name'] = br.name
                        session.state = 'select_vehicle_type'
                        session.save()

                        from master.models import VehicleType
                        vehicle_types = VehicleType.objects.filter(is_active=True, is_deleted=False)
                        if not vehicle_types.exists():
                            reply_text = "Sorry, no vehicle types are available for registration right now."
                            is_menu = False
                        else:
                            reply_text = "Please select your vehicle type:"
                            choices_list = []
                            for vt in vehicle_types:
                                choices_list.append({
                                    "title": vt.name[:24],
                                    "choice_id": f"reg_vt_{vt.id}",
                                    "id": f"reg_vt_{vt.id}",
                                    "button_id": f"reg_vt_{vt.id}",
                                    "description": vt.description[:72] if vt.description else ""
                                })
                            interactive_menu = {
                                "header_message": "",
                                "list_title": "Choose Vehicle Type",
                                "sections": [{"title": "Vehicle Types", "choices": choices_list}]
                            }
                    else:
                        reply_text = "Please select a branch from the list below:"
                        branches = company.branches.filter(is_deleted=False)
                        choices_list = []
                        for b in branches:
                            choices_list.append({
                                "title": b.name[:24],
                                "choice_id": f"reg_br_{b.id}",
                                "id": f"reg_br_{b.id}",
                                "button_id": f"reg_br_{b.id}",
                                "description": b.name[:72]
                            })
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Choose Branch",
                            "sections": [{"title": "Our Branches", "choices": choices_list}]
                        }

                elif session.state == 'scheme_select_branch':
                    from client_management.models import Branch, Scheme
                    br = find_matching_branch(company, choice, choice_id_raw, choice_title_raw, incoming_msg)
                            
                    if br:
                        today_date = get_local_date()
                        active_schemes = Scheme.objects.filter(
                            company=company,
                            is_deleted=False,
                            start_date__lte=today_date,
                            end_date__gte=today_date
                        )
                        if not active_schemes.exists():
                            reply_text = f"There are currently no active schemes at {br.name}."
                            is_menu = False
                            session.delete()
                        else:
                            msg_lines = [f"🌟 *Active Schemes at {br.name}* 🌟\n"]
                            for sch in active_schemes:
                                msg_lines.append(f"🔹 *{sch.name}*")
                                
                                scheme_services = sch.services.all()
                                if scheme_services.exists():
                                    srv_names = ", ".join([s.name for s in scheme_services])
                                    msg_lines.append(f"   Services: {srv_names}")
                                    
                                if sch.paid_visits and sch.free_visits:
                                    msg_lines.append(f"   Pay for {sch.paid_visits} washes, get {sch.free_visits} FREE!")
                                elif sch.discount_percentage:
                                    msg_lines.append(f"   Enjoy a {sch.discount_percentage}% discount!")
                                msg_lines.append(f"   Valid until: {sch.end_date.strftime('%d %b %Y')}\n")
                            
                            msg_lines.append("\nTap below to check which schemes apply to your vehicles.")
                            reply_text = "\n".join(msg_lines)
                            
                            session.data['scheme_branch_id'] = str(br.id)
                            session.state = 'scheme_show_all'
                            session.save()

                            
                            interactive_menu = {
                                "header_message": "",
                                "buttons": [
                                    {"title": "Check Eligibility", "id": "btn_check_scheme_eligibility", "button_id": "btn_check_scheme_eligibility"}
                                ]
                            }
                    else:
                        reply_text = "Please select a branch from the list below:"
                        choices_list = []
                        for b in all_branches:
                            choices_list.append({
                                "title": b.name[:24],
                                "choice_id": f"sch_br_{b.id}",
                                "id": f"sch_br_{b.id}",
                                "button_id": f"sch_br_{b.id}",
                                "description": ""
                            })
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Choose Branch",
                            "sections": [{"title": "Our Branches", "choices": choices_list}]
                        }
                        
                elif session.state == 'scheme_select_vehicle':
                    from client_management.models import Scheme
                    br_id = session.data.get('scheme_branch_id')
                    
                    vehicle_match = None
                    if choice.startswith('sch_veh_'):
                        v_id = choice.replace('sch_veh_', '').strip()
                        vehicle_match = CustomerVehicle.objects.filter(id=v_id, customer=customer, is_deleted=False).first()
                    else:
                        # Fallback for text: "Choose a vehicle to check its eligible schemes:\nKL53L8330 Normal Bus"
                        cleaned_choice = choice.lower().strip()
                        if "choose a vehicle to check" in cleaned_choice:
                            lines = [l.strip() for l in cleaned_choice.split("\n") if l.strip()]
                            if len(lines) >= 2:
                                veh_no_part = lines[1]
                                best_match = None
                                best_match_len = 0
                                option_line_cleaned = ''.join(c for c in veh_no_part.lower() if c.isalnum())
                                for v in CustomerVehicle.objects.filter(customer=customer, is_deleted=False):
                                    v_num_cleaned = ''.join(c for c in v.vehicle_number.lower() if c.isalnum())
                                    if v_num_cleaned and v_num_cleaned in option_line_cleaned:
                                        if len(v_num_cleaned) > best_match_len:
                                            best_match = v
                                            best_match_len = len(v_num_cleaned)
                                if best_match:
                                    vehicle_match = best_match
                        
                    if vehicle_match:
                        today_date = get_local_date()
                        active_schemes = Scheme.objects.filter(
                            company=company,
                            is_deleted=False,
                            start_date__lte=today_date,
                            end_date__gte=today_date,
                            vehicle_types=vehicle_match.vehicle_type
                        )
                        
                        veh_name = f"{vehicle_match.vehicle_number} {vehicle_match.vehicle_type_model.name if vehicle_match.vehicle_type_model else ''}"
                        
                        if not active_schemes.exists():
                            reply_text = f"Sorry, there are currently no active schemes eligible for your {veh_name}."
                        else:
                            msg_lines = [f"🌟 *Eligible Schemes for {veh_name}* 🌟\n"]
                            for sch in active_schemes:
                                msg_lines.append(f"✅ *{sch.name}*")
                                
                                scheme_services = sch.services.all()
                                if scheme_services.exists():
                                    srv_names = ", ".join([s.name for s in scheme_services])
                                    msg_lines.append(f"   Services: {srv_names}")
                                    
                                if sch.paid_visits and sch.free_visits:
                                    msg_lines.append(f"   Pay for {sch.paid_visits} washes, get {sch.free_visits} FREE!")
                                elif sch.discount_percentage:
                                    msg_lines.append(f"   Enjoy a {sch.discount_percentage}% discount!")
                                msg_lines.append("")

                            reply_text = "\n".join(msg_lines)
                        
                        is_menu = False
                        session.delete()
                    else:
                        reply_text = "⚠️ We couldn't identify that vehicle. Please select your vehicle from the list below:"
                        vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                        choices_list = []
                        for v in vehicles:
                            model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                            choices_list.append({
                                "title": f"{v.vehicle_number} {model_name}"[:24],
                                "choice_id": f"sch_veh_{v.id}",
                                "id": f"sch_veh_{v.id}",
                                "button_id": f"sch_veh_{v.id}",
                                "description": ""
                            })
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Choose Vehicle",
                            "sections": [{"title": "Your Vehicles", "choices": choices_list}]
                        }

                elif choice == "btn_check_scheme_eligibility":
                    if not customer:
                        reply_text = "Please register as a customer first to check scheme eligibility."
                        is_menu = False
                    else:
                        vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                        if not vehicles.exists():
                            reply_text = "⚠️ No registered vehicles found on your account. Please visit us or contact our team to add your vehicle."
                            is_menu = False
                        elif vehicles.count() == 1:
                            # Auto-check for the single vehicle
                            v = vehicles.first()
                            from client_management.models import Scheme
                            today_date = get_local_date()
                            active_schemes = Scheme.objects.filter(
                                company=company,
                                is_deleted=False,
                                start_date__lte=today_date,
                                end_date__gte=today_date,
                                vehicle_types=v.vehicle_type
                            )
                            veh_name = f"{v.vehicle_number} {v.vehicle_type_model.name if v.vehicle_type_model else ''}"
                            if not active_schemes.exists():
                                reply_text = f"Sorry, there are currently no active schemes eligible for your {veh_name}."
                            else:
                                msg_lines = [f"🌟 *Eligible Schemes for {veh_name}* 🌟\n"]
                                for sch in active_schemes:
                                    msg_lines.append(f"✅ *{sch.name}*")
                                    
                                    scheme_services = sch.services.all()
                                    if scheme_services.exists():
                                        srv_names = ", ".join([s.name for s in scheme_services])
                                        msg_lines.append(f"   Services: {srv_names}")
                                        
                                    if sch.paid_visits and sch.free_visits:
                                        msg_lines.append(f"   Pay for {sch.paid_visits} washes, get {sch.free_visits} FREE!")
                                    elif sch.discount_percentage:
                                        msg_lines.append(f"   Enjoy a {sch.discount_percentage}% discount!")
                                    msg_lines.append("")
                                reply_text = "\n".join(msg_lines)
                            is_menu = False
                            session.delete()
                        else:
                            from core.functions import get_auto_id
                            br_id = None
                            if session and session.data.get('scheme_branch_id'):
                                br_id = session.data['scheme_branch_id']
                            elif branch:
                                br_id = str(branch.id)
                                
                            session.state = 'scheme_select_vehicle'
                            session.data['scheme_branch_id'] = br_id
                            session.save()
                            
                            reply_text = "Choose a vehicle to check its eligible schemes:"
                            choices_list = []
                            for v in vehicles:
                                model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                choices_list.append({
                                    "title": f"{v.vehicle_number} {model_name}"[:24],
                                    "choice_id": f"sch_veh_{v.id}",
                                    "id": f"sch_veh_{v.id}",
                                    "button_id": f"sch_veh_{v.id}",
                                    "description": ""
                                })
                            interactive_menu = {
                                "header_message": "",
                                "list_title": "Choose Vehicle",
                                "sections": [{"title": "Your Vehicles", "choices": choices_list}]
                            }

                elif session.state == 'cancel_select_booking':
                    bk_id = None
                    if choice.startswith("cancel_bk_"):
                        bk_id = choice.replace("cancel_bk_", "").strip()
                    else:
                        # Fallback for when list ID is dropped by webhook and only title is sent
                        import re
                        match = re.search(r'bk(\d+)', choice)
                        if match:
                            found_b_num = match.group(0).upper()
                            extracted_id = match.group(1)
                            
                            fallback_b = Booking.objects.filter(
                                customer=customer, 
                                is_deleted=False
                            ).filter(
                                Q(booking_number=found_b_num) | Q(auto_id=extracted_id)
                            ).first()
                            
                            if fallback_b:
                                bk_id = str(fallback_b.id)

                    if bk_id:
                        b = Booking.objects.filter(id=bk_id, customer=customer, is_deleted=False).first()
                        if b:
                            session.state = 'cancel_confirm'
                            session.data['booking_id'] = str(b.id)
                            session.save()
                            reply_text = (
                                f"Are you sure you want to cancel this booking?\n\n"
                                f"📋 Booking No: *{b.booking_number or b.auto_id}*\n"
                                f"🚗 Vehicle: {b.vehicle.vehicle_number}\n"
                                f"📅 Date: {b.booking_date.strftime('%d %b %Y')}"
                            )
                            interactive_menu = {
                                "header_message": "",
                                "buttons": [
                                    {"title": "❌ Yes, Cancel", "id": "btn_confirm_cancel_yes", "button_id": "btn_confirm_cancel_yes"},
                                    {"title": "🔙 No, Keep It", "id": "btn_confirm_cancel_no", "button_id": "btn_confirm_cancel_no"}
                                ]
                            }
                        else:
                            reply_text = "⚠️ Invalid booking selected. Please try again."
                            is_menu = False
                            session.delete()
                    else:
                        reply_text = "Please select a booking from the list."
                        is_menu = False
                        
                elif session.state == 'cancel_confirm':
                    bk_id = session.data.get('booking_id')
                    b = Booking.objects.filter(id=bk_id, customer=customer, is_deleted=False).first()
                    
                    if choice == "btn_confirm_cancel_yes":
                        if b:
                            b.status = Booking.STATUS_CANCELLED
                            b.save()
                            reply_text = f"✅ Your booking *{b.booking_number or b.auto_id}* has been successfully cancelled."
                        else:
                            reply_text = "⚠️ We couldn't find that booking."
                        is_menu = False
                        session.delete()
                    elif choice == "btn_confirm_cancel_no":
                        if b:
                            reply_text = f"Okay! Your booking *{b.booking_number or b.auto_id}* remains active. We look forward to seeing you! 🫧"
                        else:
                            reply_text = "Cancellation aborted."
                        is_menu = False
                        session.delete()
                    else:
                        reply_text = "Please tap 'Yes, Cancel' or 'No, Keep It'."
                        is_menu = False

                elif session.state == 'loc_select_branch':
                    from client_management.models import Branch
                    br = find_matching_branch(company, choice, choice_id_raw, choice_title_raw, incoming_msg)
                        
                    if br:
                        reply_text = ""
                        lat, lng = '11.2588', '75.7804'
                        if 'puthencruz' in br.name.lower():
                            lat, lng = '9.9706', '76.4252'
                        elif 'mannarkkad' in br.name.lower() or 'rasna' in br.name.lower():
                            lat, lng = '10.9800', '76.4700'
                        location_pin = {'lat': lat, 'lng': lng, 'address': br.name}
                        is_menu = False
                        session.delete()
                    else:
                        reply_text = "Please select a branch from the list."
                        is_menu = False
                        
                elif session.state == 'contact_select_branch':
                    from client_management.models import Branch
                    br = find_matching_branch(company, choice, choice_id_raw, choice_title_raw, incoming_msg)
                        
                    if br:
                        lines = [f"📞 *Contact Us: {br.name}*"]
                        if br.phone:
                            lines.append(f"Phone: {br.phone}")
                        if br.email:
                            lines.append(f"Email: {br.email}")
                        reply_text = "\n".join(lines)
                        if len(lines) == 1:
                            reply_text += "\nNo contact details available for this branch."
                        is_menu = False
                        session.delete()
                    else:
                        reply_text = "Please select a branch from the list."
                        is_menu = False

                elif session.state == 'book_select_branch':
                    from client_management.models import Branch
                    all_branches = company.branches.filter(is_deleted=False)
                    br = find_matching_branch(company, choice, choice_id_raw, choice_title_raw, incoming_msg)

                    if br:
                        session.data['booking_branch_id'] = str(br.id)
                        session.data['booking_branch_name'] = br.name
                        session.state = 'book_select_date'
                        session.save()
                        
                        from .utils import validate_booking
                        today_date = get_local_date()
                        tomorrow_date = today_date + timedelta(days=1)
                        
                        today_ok, _ = validate_booking(br, today_date)
                        tomorrow_ok, _ = validate_booking(br, tomorrow_date)
                        
                        date_buttons = []
                        if today_ok:
                            date_buttons.append({ "title": "Today", "button_id": "book_date_today", "id": "book_date_today" })
                        if tomorrow_ok:
                            date_buttons.append({ "title": "Tomorrow", "button_id": "book_date_tomorrow", "id": "book_date_tomorrow" })
                            
                        if not date_buttons:
                            reply_text = f"Sorry, bookings are currently closed or full for today and tomorrow at {br.name}."
                            is_menu = False
                        else:
                            reply_text = f"Bookings are open for {br.name}! Please select the booking date below:"
                            interactive_menu = {
                                "header_message": "",
                                "buttons": date_buttons
                            }
                    else:
                        reply_text = "Please select a branch from the list below:"
                        choices_list = []
                        for b in all_branches:
                            choices_list.append({
                                "title": b.name[:24],
                                "choice_id": f"reg_br_{b.id}",
                                "id": f"reg_br_{b.id}",
                                "button_id": f"reg_br_{b.id}",
                                "description": b.name[:72]
                            })
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Choose Branch",
                            "sections": [{"title": "Our Branches", "choices": choices_list}]
                        }



                elif session.state == 'book_select_date':
                    cleaned_choice = choice.lower().strip()
                    target_day = None
                    if "today" in cleaned_choice or choice == "book_date_today":
                        target_day = "today"
                    elif "tomorrow" in cleaned_choice or "tom" in cleaned_choice or choice == "book_date_tomorrow":
                        target_day = "tomorrow"
                        
                    if target_day:
                        session.data['booking_date_str'] = target_day
                        session.state = 'book_select_vehicle'
                        session.save()
                        
                        br_id = session.data.get('booking_branch_id')
                        from client_management.models import Branch
                        br = Branch.objects.get(id=br_id)
                        
                        vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                        if not vehicles.exists():
                            reply_text = "\u26a0\ufe0f No registered vehicles found on your account. Please visit us or contact our team to add your vehicle."
                            is_menu = False
                            session.delete()
                        elif vehicles.count() == 1:
                            # Only one vehicle — go straight to service selection
                            v = vehicles.first()
                            booking_date = get_local_date()
                            if target_day == "tomorrow":
                                booking_date += timedelta(days=1)
                            from .utils import validate_booking
                            is_valid, validation_msg = validate_booking(br, booking_date)
                            if not is_valid:
                                reply_text = f"\u26a0\ufe0f We're unable to accept bookings for {booking_date.strftime('%d-%b-%Y')}: {validation_msg}. Please try another date."
                                is_menu = False
                                session.delete()
                            else:
                                available_services = _get_available_services(br, v)
                                session.data['booking_vehicle_id'] = str(v.id)
                                session.data['booking_date_resolved'] = str(booking_date)
                                session.state = 'book_select_service'
                                session.save()
                                if not available_services:
                                    # No services configured — confirm booking directly
                                    from core.functions import get_auto_id
                                    bk_num = f"BK{get_auto_id(Booking)}"
                                    safe_create_model(
                                        Booking,
                                        customer=customer, vehicle=v, branch=br,
                                        booking_date=booking_date, booking_number=bk_num,
                                        status=Booking.STATUS_PENDING
                                    )
                                    model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                    reply_text = (
                                        f"\u2705 *Booking Confirmed!*\n\n"
                                        f"\U0001f4cb Booking No: *{bk_num}*\n"
                                        f"\U0001f697 Vehicle: {v.vehicle_number} {model_name}\n"
                                        f"\U0001f4c5 Date: {booking_date.strftime('%d %b %Y')}\n"
                                        f"\U0001f4cd Branch: {br.name}\n\n"
                                        f"We look forward to serving you! \U0001f9fc"
                                    )
                                    session.delete()
                                    is_menu = False
                                else:
                                    reply_text, interactive_menu = _build_service_or_category_menu(br, v, available_services)
                        else:
                            reply_text = f"Choose a vehicle to book for {target_day.capitalize()}:"
                            choices_list = []
                            for v in vehicles:
                                model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                full_desc = f"{v.vehicle_number} {model_name}".strip()
                                choices_list.append({
                                    "title": full_desc[:24],
                                    "choice_id": f"book_veh_{v.id}_{target_day}",
                                    "id": f"book_veh_{v.id}_{target_day}",
                                    "button_id": f"book_veh_{v.id}_{target_day}",
                                    "description": full_desc[:72]
                                })
                            interactive_menu = {
                                "header_message": "",
                                "list_title": "Choose Vehicle",
                                "sections": [{"title": "Your Vehicles", "choices": choices_list}]
                            }
                    else:
                        reply_text = "Please select Today or Tomorrow to continue."
                        br_id = session.data.get('booking_branch_id')
                        from client_management.models import Branch
                        br = Branch.objects.get(id=br_id)
                        
                        from .utils import validate_booking
                        today_date = get_local_date()
                        tomorrow_date = today_date + timedelta(days=1)
                        
                        today_ok, _ = validate_booking(br, today_date)
                        tomorrow_ok, _ = validate_booking(br, tomorrow_date)
                        
                        date_buttons = []
                        if today_ok:
                            date_buttons.append({ "title": "Today", "button_id": "book_date_today", "id": "book_date_today" })
                        if tomorrow_ok:
                            date_buttons.append({ "title": "Tomorrow", "button_id": "book_date_tomorrow", "id": "book_date_tomorrow" })
                        
                        interactive_menu = {
                            "header_message": "",
                            "buttons": date_buttons
                        }

                elif session.state == 'book_select_vehicle':
                    cleaned_choice = choice.lower().strip()
                    target_day = session.data.get('booking_date_str')
                    
                    veh_no_part = ""
                    vehicle_match = None
                    
                    if "choose a vehicle to book for" in cleaned_choice:
                        lines = [l.strip() for l in cleaned_choice.split("\n") if l.strip()]
                        if len(lines) >= 2:
                            header_line = lines[0]
                            if "tomorrow" in header_line:
                                target_day = "tomorrow"
                            elif "today" in header_line:
                                target_day = "today"
                            veh_no_part = lines[1]
                    else:
                        if " today" in cleaned_choice:
                            veh_no_part = cleaned_choice.split(" today")[0].strip()
                        elif " tom" in cleaned_choice:
                            veh_no_part = cleaned_choice.split(" tom")[0].strip()
                        else:
                            veh_no_part = cleaned_choice
                    
                    if veh_no_part:
                        best_match = None
                        best_match_len = 0
                        option_line_cleaned = ''.join(c for c in veh_no_part.lower() if c.isalnum())
                        for v in CustomerVehicle.objects.filter(customer=customer, is_deleted=False):
                            v_num_cleaned = ''.join(c for c in v.vehicle_number.lower() if c.isalnum())
                            if v_num_cleaned and v_num_cleaned in option_line_cleaned:
                                if len(v_num_cleaned) > best_match_len:
                                    best_match = v
                                    best_match_len = len(v_num_cleaned)
                        vehicle_match = best_match
                        
                    if not vehicle_match and choice.startswith('book_veh_'):
                        parts = choice.split("_")
                        vehicle_id = parts[2]
                        vehicle_match = CustomerVehicle.objects.filter(id=vehicle_id, customer=customer).first()
                        
                    # Also try matching via description (full "vehicle_number model" string)
                    if not vehicle_match:
                        desc_candidate = (choice_title_raw or choice or '').strip()
                        if desc_candidate:
                            for v in CustomerVehicle.objects.filter(customer=customer, is_deleted=False):
                                v_num_clean = ''.join(c for c in v.vehicle_number.lower() if c.isalnum())
                                cand_clean = ''.join(c for c in desc_candidate.lower() if c.isalnum())
                                if v_num_clean and v_num_clean in cand_clean:
                                    vehicle_match = v
                                    break

                    if vehicle_match:
                        booking_date = get_local_date()
                        if target_day == "tomorrow":
                            booking_date += timedelta(days=1)

                        br_id = session.data.get('booking_branch_id')
                        from client_management.models import Branch
                        br = Branch.objects.get(id=br_id)

                        from .utils import validate_booking
                        is_valid, validation_msg = validate_booking(br, booking_date)
                        if not is_valid:
                            reply_text = f"⚠️ We're unable to accept bookings for {booking_date.strftime('%d-%b-%Y')}: {validation_msg}. Please try another date."
                            is_menu = False
                        else:
                            available_services = _get_available_services(br, vehicle_match)

                            session.data['booking_vehicle_id'] = str(vehicle_match.id)
                            session.data['booking_date_resolved'] = str(booking_date)
                            session.state = 'book_select_service'
                            session.save()

                            if not available_services:
                                # No services found — skip service step and create booking directly
                                session.data['booking_service_name'] = ''
                                session.save()
                                from core.functions import get_auto_id
                                bk_num = f"BK{get_auto_id(Booking)}"
                                booking = safe_create_model(
                                    Booking,
                                    customer=customer,
                                    vehicle=vehicle_match,
                                    branch=br,
                                    booking_date=booking_date,
                                    booking_number=bk_num,
                                    status=Booking.STATUS_PENDING
                                )
                                veh_model = vehicle_match.vehicle_type_model.name if vehicle_match.vehicle_type_model else ""
                                reply_text = (
                                    f"✅ *Booking Confirmed!*\n\n"
                                    f"📋 Booking No: *{bk_num}*\n"
                                    f"🚗 Vehicle: {vehicle_match.vehicle_number} {veh_model}\n"
                                    f"📅 Date: {booking_date.strftime('%d %b %Y')}\n"
                                    f"📍 Branch: {br.name}\n\n"
                                    f"We look forward to serving you! 🫧"
                                )
                                session.delete()
                                is_menu = False
                            else:
                                # Ask which service
                                reply_text, interactive_menu = _build_service_or_category_menu(br, vehicle_match, available_services)
                    else:
                        reply_text = "⚠️ We couldn't identify that vehicle. Please select your vehicle from the list below."
                        br_id = session.data.get('booking_branch_id')
                        from client_management.models import Branch
                        br = Branch.objects.get(id=br_id)
                        
                        vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                        choices_list = []
                        for v in vehicles:
                            model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                            choices_list.append({
                                "title": f"{v.vehicle_number} {model_name}"[:24],
                                "choice_id": f"book_veh_{v.id}_{target_day}",
                                "id": f"book_veh_{v.id}_{target_day}",
                                "button_id": f"book_veh_{v.id}_{target_day}",
                                "description": ""
                            })
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Choose Vehicle",
                            "sections": [{"title": "Your Vehicles", "choices": choices_list}]
                        }

                elif session.state == 'book_select_service':

                    from service_management.models import Service as ServiceModel, ServiceType
                    selected_svc = None

                    # 1. Check if user selected a Category (book_cat_<id>)
                    cat_id = None
                    if choice.startswith('book_cat_'):
                        cat_id = choice.replace('book_cat_', '').strip()
                    else:
                        st = ServiceType.objects.filter(is_deleted=False).filter(
                            Q(name__iexact=choice.strip()) | Q(id__iexact=choice.strip())
                        ).first()
                        if not st and choice.strip():
                            for s_type in ServiceType.objects.filter(is_deleted=False):
                                if choice[:24].lower() and s_type.name[:24].lower() == choice[:24].lower():
                                    st = s_type
                                    break
                        if st:
                            cat_id = str(st.id)

                    if cat_id:
                        vehicle_id = session.data.get('booking_vehicle_id')
                        br_id = session.data.get('booking_branch_id')
                        from client_management.models import Branch

                        br = Branch.objects.get(id=br_id)
                        vehicle_match = CustomerVehicle.objects.filter(id=vehicle_id, customer=customer).first()
                        available_services = _get_available_services(br, vehicle_match)

                        cat_services = [s for s in available_services if str(s.service_type_id) == str(cat_id)]
                        if not cat_services:
                            cat_services = available_services

                        choices_list = [_build_service_choice(svc) for svc in cat_services[:10]]
                        st_obj = ServiceType.objects.filter(id=cat_id).first()
                        cat_name = st_obj.name if st_obj else "Selected Category"

                        reply_text = f"Please select a service under *{cat_name}*:"
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Choose Service",
                            "sections": [{"title": f"{cat_name[:20]} Services", "choices": choices_list}]
                        }
                    else:
                        # 2. Check if user selected a Service (book_svc_<id>)
                        if choice.startswith('book_svc_'):
                            svc_id = choice.replace('book_svc_', '').strip()
                            selected_svc = ServiceModel.objects.filter(id=svc_id, is_active=True).first()

                        if not selected_svc:
                            selected_svc = ServiceModel.objects.filter(
                                name__iexact=choice.strip(), is_active=True, is_deleted=False
                            ).first()
                        if not selected_svc:
                            for svc in ServiceModel.objects.filter(is_active=True, is_deleted=False):
                                if svc.name[:24].lower() == choice[:24].lower():
                                    selected_svc = svc
                                    break

                        if selected_svc:
                            vehicle_id = session.data.get('booking_vehicle_id')
                            date_str = session.data.get('booking_date_resolved')
                            br_id = session.data.get('booking_branch_id')

                            from client_management.models import Branch
                            import datetime as dt_module
                            br = Branch.objects.get(id=br_id)
                            vehicle_match = CustomerVehicle.objects.filter(id=vehicle_id, customer=customer).first()
                            booking_date = dt_module.date.fromisoformat(date_str) if date_str else get_local_date()

                            try:
                                from core.functions import get_auto_id
                                bk_num = f"BK{get_auto_id(Booking)}"
                                booking = safe_create_model(
                                    Booking,
                                    customer=customer,
                                    vehicle=vehicle_match,
                                    branch=br,
                                    booking_date=booking_date,
                                    booking_number=bk_num,
                                    service=selected_svc,
                                    service_name=selected_svc.name,
                                    status=Booking.STATUS_PENDING
                                )
                                veh_model = vehicle_match.vehicle_type_model.name if vehicle_match and vehicle_match.vehicle_type_model else ""
                                reply_text = (
                                    f"✅ *Booking Confirmed!*\n\n"
                                    f"📋 Booking No: *{bk_num}*\n"
                                    f"🚗 Vehicle: {vehicle_match.vehicle_number} {veh_model}\n"
                                    f"🔧 Service: {selected_svc.name}\n"
                                    f"📅 Date: {booking_date.strftime('%d %b %Y')}\n"
                                    f"📍 Branch: {br.name}\n\n"
                                    f"We look forward to serving you! 🫧"
                                )
                                session.delete()
                            except Exception as e:
                                reply_text = f"⚠️ We encountered an issue while processing your booking. Please try again or contact our support team."
                            is_menu = False
                        else:
                            # Show category or service menu again
                            vehicle_id = session.data.get('booking_vehicle_id')
                            br_id = session.data.get('booking_branch_id')
                            from client_management.models import Branch

                            br = Branch.objects.get(id=br_id)
                            vehicle_match = CustomerVehicle.objects.filter(id=vehicle_id, customer=customer).first()
                            available_services = _get_available_services(br, vehicle_match)

                            reply_text, interactive_menu = _build_service_or_category_menu(br, vehicle_match, available_services)
                            if not reply_text:
                                reply_text = "⚠️ Could not identify that service."
                                is_menu = False

                elif session.state == 'select_vehicle_type':
                    from master.models import VehicleType, VehicleTypeModel
                    
                    # Look up by name first (since wawy.org returns title) or fallback to ID
                    vt = VehicleType.objects.filter(name__iexact=choice, is_active=True, is_deleted=False).first()
                    if not vt and choice.startswith('reg_vt_'):
                        vt_id = choice.replace('reg_vt_', '').strip()
                        vt = VehicleType.objects.filter(id=vt_id, is_active=True, is_deleted=False).first()

                    if vt:
                        try:
                            session.data['vehicle_type_id'] = str(vt.id)
                            session.data['vehicle_type_name'] = vt.name
                            
                            models_qs = VehicleTypeModel.objects.filter(vehicle_type=vt, is_active=True, is_deleted=False)
                            if not models_qs.exists():
                                reply_text = "Please reply with your vehicle registration number (e.g. KL53K8990):"
                                session.state = 'awaiting_vehicle_number'
                                session.save()
                                is_menu = False
                            else:
                                session.state = 'select_vehicle_model'
                                session.save()
                                
                                reply_text = f"Please select the model of your {vt.name}:"
                                choices_list = []
                                for vtm in models_qs[:10]:
                                    choices_list.append({
                                        "title": vtm.name[:20],
                                        "choice_id": f"reg_vtm_{vtm.id}",
                                        "id": f"reg_vtm_{vtm.id}",
                                        "button_id": f"reg_vtm_{vtm.id}",
                                        "description": vtm.description[:72] if vtm.description else ""
                                    })
                                interactive_menu = {
                                    "header_message": "Select Model",
                                    "list_title": "Choose Model",
                                    "sections": [
                                        {
                                            "title": "Available Models",
                                            "choices": choices_list
                                        }
                                    ]
                                }
                        except Exception:
                            reply_text = "Invalid vehicle type. Please select your vehicle type:"
                            vehicle_types = VehicleType.objects.filter(is_active=True, is_deleted=False)
                            choices_list = [{
                                "title": vt.name[:20],
                                "choice_id": f"reg_vt_{vt.id}",
                                "id": f"reg_vt_{vt.id}",
                                "button_id": f"reg_vt_{vt.id}"
                            } for vt in vehicle_types]
                            interactive_menu = {
                                "header_message": "Select Vehicle Type",
                                "list_title": "Choose Vehicle Type",
                                "sections": [{"title": "Vehicle Types", "choices": choices_list}]
                            }
                    else:
                        reply_text = "Please select a vehicle type from the list to continue."
                        vehicle_types = VehicleType.objects.filter(is_active=True, is_deleted=False)
                        choices_list = [{
                            "title": vt.name[:20],
                            "choice_id": f"reg_vt_{vt.id}",
                            "id": f"reg_vt_{vt.id}",
                            "button_id": f"reg_vt_{vt.id}"
                        } for vt in vehicle_types]
                        interactive_menu = {
                            "header_message": "Select Vehicle Type",
                            "list_title": "Choose Vehicle Type",
                            "sections": [{"title": "Vehicle Types", "choices": choices_list}]
                        }

                elif session.state == 'select_vehicle_model':
                    from master.models import VehicleTypeModel
                    vt_id = session.data.get('vehicle_type_id')
                    
                    # Look up by name first (since wawy.org returns title) or fallback to ID
                    vtm = VehicleTypeModel.objects.filter(vehicle_type_id=vt_id, name__iexact=choice, is_active=True, is_deleted=False).first()
                    if not vtm and choice.startswith('reg_vtm_'):
                        vtm_id = choice.replace('reg_vtm_', '').strip()
                        vtm = VehicleTypeModel.objects.filter(id=vtm_id, is_active=True, is_deleted=False).first()

                    if vtm:
                        try:
                            session.data['vehicle_type_model_id'] = str(vtm.id)
                            session.data['vehicle_type_model_name'] = vtm.name
                            session.state = 'awaiting_vehicle_number'
                            session.save()
                            
                            reply_text = "Please reply with your vehicle registration number (e.g. KL53K8990):"
                            is_menu = False
                        except Exception:
                            reply_text = "Invalid vehicle model. Please select the model from the list:"
                            models_qs = VehicleTypeModel.objects.filter(vehicle_type_id=vt_id, is_active=True, is_deleted=False)
                            choices_list = [{
                                "title": m.name[:20],
                                "choice_id": f"reg_vtm_{m.id}",
                                "id": f"reg_vtm_{m.id}",
                                "button_id": f"reg_vtm_{m.id}"
                            } for m in models_qs[:10]]
                            interactive_menu = {
                                "header_message": "Select Model",
                                "list_title": "Choose Model",
                                "sections": [{"title": "Available Models", "choices": choices_list}]
                            }
                    else:
                        reply_text = "Please select a vehicle model from the list to continue."
                        models_qs = VehicleTypeModel.objects.filter(vehicle_type_id=vt_id, is_active=True, is_deleted=False)
                        choices_list = [{
                            "title": m.name[:20],
                            "choice_id": f"reg_vtm_{m.id}",
                            "id": f"reg_vtm_{m.id}",
                            "button_id": f"reg_vtm_{m.id}"
                        } for m in models_qs[:10]]
                        interactive_menu = {
                            "header_message": "Select Model",
                            "list_title": "Choose Model",
                            "sections": [{"title": "Available Models", "choices": choices_list}]
                        }

                elif session.state == 'awaiting_vehicle_number':
                    veh_number = (incoming_msg or '').strip()
                    if not veh_number:
                        reply_text = "Vehicle registration number cannot be empty. Please enter your vehicle number:"
                        is_menu = False
                    else:
                        session.data['vehicle_number'] = veh_number
                        session.state = 'awaiting_name'
                        session.save()
                        
                        reply_text = "Thank you! Please reply with your full name:"
                        is_menu = False

                elif session.state == 'awaiting_name':
                    cust_name = (incoming_msg or '').strip()
                    if not cust_name:
                        reply_text = "Name cannot be empty. Please reply with your full name:"
                        is_menu = False
                    else:
                        from client_management.models import CustomerType
                        from core.functions import get_auto_id
                        
                        try:
                            cust_type = CustomerType.objects.filter(is_deleted=False).first()
                            if not cust_type:
                                cust_type = CustomerType.objects.first()
                                
                            session_branch_id = session.data.get('branch_id')
                            if session_branch_id:
                                from client_management.models import Branch
                                branch = Branch.objects.filter(id=session_branch_id).first() or branch

                            new_customer = safe_create_model(
                                Customer,
                                company=company,
                                branch=branch,
                                name=cust_name,
                                phone=from_phone,
                                whatsapp_number=from_phone,
                                customer_type=cust_type,
                                auto_id=get_auto_id(Customer)
                            )
                            
                            vtm_id = session.data.get('vehicle_type_model_id')
                            vt_id = session.data.get('vehicle_type_id')
                            
                            new_vehicle = safe_create_model(
                                CustomerVehicle,
                                customer=new_customer,
                                vehicle_type_id=vt_id,
                                vehicle_type_model_id=vtm_id,
                                vehicle_number=session.data['vehicle_number'].upper(),
                                auto_id=get_auto_id(CustomerVehicle)
                            )
                            
                            session.delete()
                            
                            booking_setting = BookingSettings.objects.filter(branch=branch).first()
                            if booking_setting and not booking_setting.is_booking_enabled:
                                reply_text = (
                                    f"✅ Registration successful!\n\nHi *{new_customer.name}*, welcome to *{company.company_name}*! ❤️\n\n"
                                    f"Bookings are currently paused for this branch. We'll notify you when they reopen."
                                )
                                is_menu = False
                            else:
                                from .utils import validate_booking
                                today_date = get_local_date()
                                tomorrow_date = today_date + timedelta(days=1)
                                
                                today_ok, _ = validate_booking(branch, today_date)
                                tomorrow_ok, _ = validate_booking(branch, tomorrow_date)
                                
                                date_buttons = []
                                if today_ok:
                                    date_buttons.append({ "title": "Today", "button_id": "book_date_today", "id": "book_date_today" })
                                if tomorrow_ok:
                                    date_buttons.append({ "title": "Tomorrow", "button_id": "book_date_tomorrow", "id": "book_date_tomorrow" })
                                    
                                if not date_buttons:
                                    reply_text = (
                                        f"✅ Registration successful!\n\nHi *{new_customer.name}*, welcome to *{company.company_name}*! ❤️\n\n"
                                        f"Bookings are currently fully booked for today and tomorrow. Please check back soon!"
                                    )
                                    is_menu = False
                                else:
                                    reply_text = (
                                        f"✅ Registration successful!\n\nHi *{new_customer.name}*, welcome to *{company.company_name}*! ❤️\n\n"
                                        f"Please select your preferred booking date below:"
                                    )
                                    interactive_menu = {
                                        "header_message": "Select Date",
                                        "buttons": date_buttons
                                    }
                        except Exception as e:
                            reply_text = f"⚠️ We encountered an issue while creating your account. Please try again by sending your full name:"
                            is_menu = False

                    response_text = send_whatsapp_simple(from_phone, reply_text, setting=setting, interactive_data=interactive_menu)
                    status_str = 'Sent' if ('success' in response_text.lower() or 'wa_' in response_text.lower()) else 'Failed'
                    safe_create_model(
                        WhatsAppMessage,
                        company=company,
                        recipient_number=from_phone,
                        message=reply_text,
                        status=status_str
                    )
                    return HttpResponse('OK', status=200)


            elif "scheme" in choice or choice == "menu_schemes":
                from core.functions import get_auto_id
                from client_management.models import Scheme
                
                branches = company.branches.filter(is_deleted=False)
                branch_count = branches.count()
                
                if branch_count > 1:
                    ChatSession.objects.update_or_create(
                        phone_number=from_phone,
                        defaults={
                            'state': 'scheme_select_branch',
                            'data': {},
                            'auto_id': get_auto_id(ChatSession)
                        }
                    )
                    reply_text = "Please select a branch to view active schemes:"
                    choices_list = []
                    for b in branches:
                        choices_list.append({
                            "title": b.name[:24],
                            "choice_id": f"sch_br_{b.id}",
                            "id": f"sch_br_{b.id}",
                            "button_id": f"sch_br_{b.id}",
                            "description": b.name[:72]
                        })
                    interactive_menu = {
                        "header_message": "",
                        "list_title": "Choose Branch",
                        "sections": [{"title": "Our Branches", "choices": choices_list}]
                    }
                else:
                    br = branches.first()
                    today_date = get_local_date()
                    active_schemes = Scheme.objects.filter(
                        company=company,
                        is_deleted=False,
                        start_date__lte=today_date,
                        end_date__gte=today_date
                    )
                    if not active_schemes.exists():
                        reply_text = f"There are currently no active schemes available."
                        is_menu = False
                    else:
                        msg_lines = [f"🌟 *Active Schemes* 🌟\n"]
                        for sch in active_schemes:
                            msg_lines.append(f"🔹 *{sch.name}*")
                            
                            scheme_services = sch.services.all()
                            if scheme_services.exists():
                                srv_names = ", ".join([s.name for s in scheme_services])
                                msg_lines.append(f"   Services: {srv_names}")
                                
                            if sch.paid_visits and sch.free_visits:
                                msg_lines.append(f"   Pay for {sch.paid_visits} washes, get {sch.free_visits} FREE!")
                            elif sch.discount_percentage:
                                msg_lines.append(f"   Enjoy a {sch.discount_percentage}% discount!")
                            msg_lines.append(f"   Valid until: {sch.end_date.strftime('%d %b %Y')}\n")

                        
                        msg_lines.append("\nTap below to check which schemes apply to your vehicles.")
                        reply_text = "\n".join(msg_lines)
                        
                        ChatSession.objects.update_or_create(
                            phone_number=from_phone,
                            defaults={
                                'state': 'scheme_show_all',
                                'data': {'scheme_branch_id': str(br.id) if br else None},
                                'auto_id': get_auto_id(ChatSession)
                            }
                        )
                        
                        interactive_menu = {
                            "header_message": "",
                            "buttons": [
                                {"title": "Check Eligibility", "id": "btn_check_scheme_eligibility", "button_id": "btn_check_scheme_eligibility"}
                            ]
                        }
            elif choice == "menu_book" or choice == "book an appointment" or (choice == "book" and not choice.startswith("book_date_") and not choice.startswith("book_veh_")):
                if not customer:
                    from master.models import VehicleType
                    vehicle_types = VehicleType.objects.filter(is_active=True, is_deleted=False)
                    if not vehicle_types.exists():
                        reply_text = "Sorry, no vehicle types are available for registration right now."
                        is_menu = False
                    else:
                        from core.functions import get_auto_id
                        branches = company.branches.filter(is_deleted=False)
                        branch_count = branches.count()
                        if branch_count > 1:
                            ChatSession.objects.update_or_create(
                                phone_number=from_phone,
                                defaults={
                                    'state': 'register_select_branch',
                                    'data': {},
                                    'auto_id': get_auto_id(ChatSession)
                                }
                            )
                            reply_text = "Welcome! Let's get you registered to book appointments.\n\nPlease select a branch from the list to continue:"
                            choices_list = []
                            for b in branches:
                                choices_list.append({
                                    "title": b.name[:24],
                                    "choice_id": f"reg_br_{b.id}",
                                    "id": f"reg_br_{b.id}",
                                    "button_id": f"reg_br_{b.id}",
                                    "description": b.name[:72]
                                })
                            interactive_menu = {
                                "header_message": "",
                                "list_title": "Choose Branch",
                                "sections": [{"title": "Our Branches", "choices": choices_list}]
                            }
                        else:
                            initial_data = {}
                            if branch_count == 1:
                                initial_data['branch_id'] = str(branches.first().id)
                                initial_data['branch_name'] = branches.first().name

                            ChatSession.objects.update_or_create(
                                phone_number=from_phone,
                                defaults={
                                    'state': 'select_vehicle_type',
                                    'data': initial_data,
                                    'auto_id': get_auto_id(ChatSession)
                                }
                            )
                            reply_text = "Welcome! Let's get you registered to book appointments.\n\nPlease select your vehicle type:"
                            choices_list = []
                            for vt in vehicle_types:
                                choices_list.append({
                                    "title": vt.name[:20],
                                    "choice_id": f"reg_vt_{vt.id}",
                                    "id": f"reg_vt_{vt.id}",
                                    "button_id": f"reg_vt_{vt.id}",
                                    "description": vt.description[:72] if vt.description else ""
                                })
                            interactive_menu = {
                                "header_message": "",
                                "list_title": "Choose Vehicle Type",
                                "sections": [
                                    {
                                        "title": "Vehicle Types",
                                        "choices": choices_list
                                    }
                                ]
                            }
                elif not branch:
                    reply_text = "Sorry, no active branch is associated with your account."
                    is_menu = False
                else:
                    branches = company.branches.filter(is_deleted=False)
                    branch_count = branches.count()
                    if branch_count > 1:
                        from core.functions import get_auto_id
                        ChatSession.objects.update_or_create(
                            phone_number=from_phone,
                            defaults={
                                'state': 'book_select_branch',
                                'data': {},
                                'auto_id': get_auto_id(ChatSession)
                            }
                        )
                        reply_text = "Please select the branch you would like to book at:"
                        choices_list = []
                        for b in branches:
                            choices_list.append({
                                "title": b.name[:24],
                                "choice_id": f"reg_br_{b.id}",
                                "id": f"reg_br_{b.id}",
                                "button_id": f"reg_br_{b.id}",
                                "description": b.name[:72]
                            })
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Choose Branch",
                            "sections": [{"title": "Our Branches", "choices": choices_list}]
                        }
                    else:
                        # Check if booking is enabled
                        booking_setting = BookingSettings.objects.filter(branch=branch).first()
                        if booking_setting and not booking_setting.is_booking_enabled:
                            reply_text = "Sorry, bookings are currently disabled for this branch."
                            is_menu = False
                        else:
                            from .utils import validate_booking
                            today_date = get_local_date()
                            tomorrow_date = today_date + timedelta(days=1)
                            
                            today_ok, _ = validate_booking(branch, today_date)
                            tomorrow_ok, _ = validate_booking(branch, tomorrow_date)
                            
                            date_buttons = []
                            if today_ok:
                                date_buttons.append({ "title": "Today", "button_id": "book_date_today", "id": "book_date_today" })
                            if tomorrow_ok:
                                date_buttons.append({ "title": "Tomorrow", "button_id": "book_date_tomorrow", "id": "book_date_tomorrow" })
                                
                            if not date_buttons:
                                reply_text = "Sorry, bookings are currently closed or full for today and tomorrow."
                                is_menu = False
                            else:
                                reply_text = "Bookings are open! Please select the booking date below:"
                                interactive_menu = {
                                    "header_message": "Select Date",
                                    "buttons": date_buttons
                                }
            elif choice == "book_date_today" or choice == "today":
                if not customer or not branch:
                    reply_text = "Please register as a customer first to use our booking services."
                    is_menu = False
                else:
                    booking_date = get_local_date()
                    from .utils import validate_booking
                    is_valid, validation_msg = validate_booking(branch, booking_date)
                    if not is_valid:
                        reply_text = f"⚠️ Today is unavailable for booking: {validation_msg}. Please try booking for Tomorrow."
                        is_menu = False
                    else:
                        vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                        if not vehicles.exists():
                            reply_text = "⚠️ No registered vehicles found on your account. Please visit us or contact our team to add your vehicle."
                            is_menu = False
                        elif vehicles.count() == 1:
                            # Only one vehicle — check for available services before confirming
                            v = vehicles.first()
                            available_services = _get_available_services(branch, v)
                            if available_services:
                                from core.functions import get_auto_id
                                ChatSession.objects.update_or_create(
                                    phone_number=from_phone,
                                    defaults={
                                        'state': 'book_select_service',
                                        'data': {
                                            'booking_date_str': 'today',
                                            'booking_date_resolved': str(booking_date),
                                            'booking_branch_id': str(branch.id),
                                            'booking_vehicle_id': str(v.id),
                                        },
                                        'auto_id': get_auto_id(ChatSession)
                                    }
                                )
                                choices_list = [_build_service_choice(svc) for svc in available_services]
                                reply_text = "Please select the service you'd like to book:"
                                interactive_menu = {
                                    "header_message": "",
                                    "list_title": "Choose Service",
                                    "sections": [{"title": "Available Services", "choices": choices_list}]
                                }
                            else:
                                # No services configured — confirm directly
                                from core.functions import get_auto_id
                                bk_num = f"BK{get_auto_id(Booking)}"
                                booking = safe_create_model(
                                    Booking,
                                    customer=customer,
                                    vehicle=v,
                                    branch=branch,
                                    booking_date=booking_date,
                                    booking_number=bk_num,
                                    status=Booking.STATUS_PENDING
                                )
                                model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                reply_text = (
                                    f"✅ *Booking Confirmed!*\n\n"
                                    f"📋 Booking No: *{bk_num}*\n"
                                    f"🚗 Vehicle: {v.vehicle_number} {model_name}\n"
                                    f"📅 Date: {booking_date.strftime('%d %b %Y')}\n"
                                    f"📍 Branch: {branch.name}\n\n"
                                    f"We look forward to serving you! 🫧"
                                )
                                is_menu = False
                        else:
                            from core.functions import get_auto_id
                            ChatSession.objects.update_or_create(
                                phone_number=from_phone,
                                defaults={
                                    'state': 'book_select_vehicle',
                                    'data': {
                                        'booking_date_str': 'today',
                                        'booking_branch_id': str(branch.id)
                                    },
                                    'auto_id': get_auto_id(ChatSession)
                                }
                            )
                            reply_text = "Choose a vehicle to book for Today:"
                            choices_list = []
                            for v in vehicles:
                                model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                choices_list.append({
                                    "title": f"{v.vehicle_number} {model_name}"[:24],
                                    "choice_id": f"book_veh_{v.id}_today",
                                    "id": f"book_veh_{v.id}_today",
                                    "button_id": f"book_veh_{v.id}_today",
                                    "description": ""
                                })
                            interactive_menu = {
                                "header_message": "",
                                "list_title": "Choose Vehicle",
                                "sections": [{"title": "Your Vehicles", "choices": choices_list}]
                            }
            elif choice == "book_date_tomorrow" or choice == "tomorrow":
                if not customer or not branch:
                    reply_text = "Please register as a customer first to use our booking services."
                    is_menu = False
                else:
                    booking_date = get_local_date() + timedelta(days=1)
                    from .utils import validate_booking
                    is_valid, validation_msg = validate_booking(branch, booking_date)
                    if not is_valid:
                        reply_text = f"⚠️ Tomorrow ({booking_date.strftime('%d %b %Y')}) is unavailable for booking: {validation_msg}. Please try booking for Today instead."
                        is_menu = False
                    else:
                        vehicles = CustomerVehicle.objects.filter(customer=customer, is_deleted=False)
                        if not vehicles.exists():
                            reply_text = "No registered vehicles found. Please add a vehicle to your account first."
                            is_menu = False
                        elif vehicles.count() == 1:
                            # Only one vehicle — check for available services before confirming
                            v = vehicles.first()
                            available_services = _get_available_services(branch, v)
                            if available_services:
                                from core.functions import get_auto_id
                                ChatSession.objects.update_or_create(
                                    phone_number=from_phone,
                                    defaults={
                                        'state': 'book_select_service',
                                        'data': {
                                            'booking_date_str': 'tomorrow',
                                            'booking_date_resolved': str(booking_date),
                                            'booking_branch_id': str(branch.id),
                                            'booking_vehicle_id': str(v.id),
                                        },
                                        'auto_id': get_auto_id(ChatSession)
                                    }
                                )
                                choices_list = [_build_service_choice(svc) for svc in available_services]
                                reply_text = "Please select the service you'd like to book:"
                                interactive_menu = {
                                    "header_message": "",
                                    "list_title": "Choose Service",
                                    "sections": [{"title": "Available Services", "choices": choices_list}]
                                }
                            else:
                                # No services configured — confirm directly
                                from core.functions import get_auto_id
                                bk_num = f"BK{get_auto_id(Booking)}"
                                booking = safe_create_model(
                                    Booking,
                                    customer=customer,
                                    vehicle=v,
                                    branch=branch,
                                    booking_date=booking_date,
                                    booking_number=bk_num,
                                    status=Booking.STATUS_PENDING
                                )
                                model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                reply_text = (
                                    f"✅ *Booking Confirmed!*\n\n"
                                    f"📋 Booking No: *{bk_num}*\n"
                                    f"🚗 Vehicle: {v.vehicle_number} {model_name}\n"
                                    f"📅 Date: {booking_date.strftime('%d %b %Y')}\n"
                                    f"📍 Branch: {branch.name}\n\n"
                                    f"We look forward to serving you! 🫧"
                                )
                                is_menu = False
                        else:
                            from core.functions import get_auto_id
                            ChatSession.objects.update_or_create(
                                phone_number=from_phone,
                                defaults={
                                    'state': 'book_select_vehicle',
                                    'data': {
                                        'booking_date_str': 'tomorrow',
                                        'booking_branch_id': str(branch.id)
                                    },
                                    'auto_id': get_auto_id(ChatSession)
                                }
                            )
                            reply_text = "Choose a vehicle to book for Tomorrow:"
                            choices_list = []
                            for v in vehicles:
                                model_name = v.vehicle_type_model.name if v.vehicle_type_model else ""
                                choices_list.append({
                                    "title": f"{v.vehicle_number} {model_name}"[:24],
                                    "choice_id": f"book_veh_{v.id}_tomorrow",
                                    "id": f"book_veh_{v.id}_tomorrow",
                                    "button_id": f"book_veh_{v.id}_tomorrow",
                                    "description": ""
                                })
                            interactive_menu = {
                                "header_message": "",
                                "list_title": "Choose Vehicle",
                                "sections": [{"title": "Your Vehicles", "choices": choices_list}]
                            }
            elif is_vehicle_selection:
                if not customer:
                    reply_text = "Please register as a customer first to use our booking services."
                    is_menu = False
                else:
                    booking_date = get_local_date()
                    if day_str == "tomorrow":
                        booking_date += timedelta(days=1)

                    try:
                        if not vehicle_match:
                            reply_text = "⚠️ We could not find that vehicle on your profile. Please contact us if you need help."
                            is_menu = False
                        else:
                            # Validate booking availability
                            from .utils import validate_booking
                            is_valid, validation_msg = validate_booking(branch, booking_date)
                            if not is_valid:
                                reply_text = f"⚠️ We're unable to accept bookings for {booking_date.strftime('%d-%b-%Y')}: {validation_msg}. Please try another date."
                                is_menu = False
                            else:
                                # Check for available services and prompt before creating booking
                                available_services = _get_available_services(branch, vehicle_match)
                                if available_services:
                                    from core.functions import get_auto_id
                                    if session:
                                        session.state = 'book_select_service'
                                        session.data['booking_vehicle_id'] = str(vehicle_match.id)
                                        session.data['booking_date_resolved'] = str(booking_date)
                                        session.data['booking_branch_id'] = str(branch.id)
                                        session.save()
                                    else:
                                        ChatSession.objects.update_or_create(
                                            phone_number=from_phone,
                                            defaults={
                                                'state': 'book_select_service',
                                                'data': {
                                                    'booking_date_resolved': str(booking_date),
                                                    'booking_branch_id': str(branch.id),
                                                    'booking_vehicle_id': str(vehicle_match.id),
                                                },
                                                'auto_id': get_auto_id(ChatSession)
                                            }
                                        )
                                    choices_list = [_build_service_choice(svc) for svc in available_services]
                                    reply_text = "Please select the service you'd like to book:"
                                    interactive_menu = {
                                        "header_message": "",
                                        "list_title": "Choose Service",
                                        "sections": [{"title": "Available Services", "choices": choices_list}]
                                    }
                                else:
                                    # No services configured — confirm directly
                                    from core.functions import get_auto_id
                                    bk_num = f"BK{get_auto_id(Booking)}"
                                    booking = safe_create_model(
                                        Booking,
                                        customer=customer,
                                        vehicle=vehicle_match,
                                        branch=branch,
                                        booking_date=booking_date,
                                        booking_number=bk_num,
                                        status=Booking.STATUS_PENDING
                                    )
                                    if session:
                                        session.delete()
                                    veh_model = vehicle_match.vehicle_type_model.name if vehicle_match.vehicle_type_model else ""
                                    reply_text = (
                                        f"✅ *Booking Confirmed!*\n\n"
                                        f"📋 Booking No: *{bk_num}*\n"
                                        f"🚗 Vehicle: {vehicle_match.vehicle_number} {veh_model}\n"
                                        f"📅 Date: {booking_date.strftime('%d %b %Y')}\n"
                                        f"📍 Branch: {branch.name}\n\n"
                                        f"Thank you for booking with us! We look forward to serving you. 🫧"
                                    )
                                    is_menu = False
                    except Exception as e:
                        reply_text = f"We apologise, but there was an error processing your request: {e}"
                        is_menu = False
            elif choice == "menu_cancel" or choice == "cancel" or "cancel booking" in choice:
                if not customer:
                    reply_text = "⚠️ You must be registered to cancel bookings."
                    is_menu = False
                else:
                    today_date = get_local_date()
                    active_bookings = Booking.objects.filter(
                        customer=customer,
                        status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED],
                        booking_date__gte=today_date,
                        is_deleted=False
                    ).order_by('booking_date')
                    
                    if not active_bookings.exists():
                        reply_text = "⚠️ You don't have any upcoming bookings to cancel."
                        is_menu = False
                    elif active_bookings.count() == 1:
                        b = active_bookings.first()
                        from core.functions import get_auto_id
                        ChatSession.objects.update_or_create(
                            phone_number=from_phone,
                            defaults={
                                'state': 'cancel_confirm',
                                'data': {'booking_id': str(b.id)},
                                'auto_id': get_auto_id(ChatSession)
                            }
                        )
                        reply_text = (
                            f"Are you sure you want to cancel this booking?\n\n"
                            f"📋 Booking No: *{b.booking_number or b.auto_id}*\n"
                            f"🚗 Vehicle: {b.vehicle.vehicle_number}\n"
                            f"📅 Date: {b.booking_date.strftime('%d %b %Y')}"
                        )
                        interactive_menu = {
                            "header_message": "",
                            "buttons": [
                                {"title": "❌ Yes, Cancel", "id": "btn_confirm_cancel_yes", "button_id": "btn_confirm_cancel_yes"},
                                {"title": "🔙 No, Keep It", "id": "btn_confirm_cancel_no", "button_id": "btn_confirm_cancel_no"}
                            ]
                        }
                    else:
                        from core.functions import get_auto_id
                        ChatSession.objects.update_or_create(
                            phone_number=from_phone,
                            defaults={
                                'state': 'cancel_select_booking',
                                'data': {},
                                'auto_id': get_auto_id(ChatSession)
                            }
                        )
                        reply_text = "Please select the booking you wish to cancel:"
                        choices_list = []
                        for b in active_bookings:
                            b_num = b.booking_number or f"BK{b.auto_id}"
                            choices_list.append({
                                "title": f"{b_num} - {b.booking_date.strftime('%d %b')}"[:20],
                                "choice_id": f"cancel_bk_{b.id}",
                                "id": f"cancel_bk_{b.id}",
                                "button_id": f"cancel_bk_{b.id}",
                                "description": f"Vehicle: {b.vehicle.vehicle_number}"[:72]
                            })
                        interactive_menu = {
                            "header_message": "",
                            "list_title": "Select Booking",
                            "sections": [{"title": "Upcoming Bookings", "choices": choices_list}]
                        }
            elif "status" in choice:
                reply_text = "To check your vehicle's wash status, please reply with your vehicle number or contact our branch directly. 🔍"
                is_menu = False
            elif "feedback" in choice:
                reply_text = "We'd love to hear from you! 😊 Please share your feedback or experience below, and our team will review it."
                is_menu = False
            elif "complaint" in choice:
                reply_text = "We sincerely apologise for the inconvenience. 🙏 Please describe your concern below and our team will look into it promptly."
                is_menu = False
            elif choice == "menu_location" or "location" in choice:
                branches = company.branches.filter(is_deleted=False)
                if branches.count() == 1:
                    br = branches.first()
                    reply_text = ""
                    lat, lng = '11.2588', '75.7804'
                    if 'puthencruz' in br.name.lower():
                        lat, lng = '9.9706', '76.4252'
                    elif 'mannarkkad' in br.name.lower() or 'rasna' in br.name.lower():
                        lat, lng = '10.9800', '76.4700'
                    location_pin = {'lat': lat, 'lng': lng, 'address': br.name}
                    is_menu = False
                elif branches.count() > 1:
                    from core.functions import get_auto_id
                    ChatSession.objects.update_or_create(
                        phone_number=from_phone,
                        defaults={
                            'state': 'loc_select_branch',
                            'data': {},
                            'auto_id': get_auto_id(ChatSession)
                        }
                    )
                    reply_text = "Please select a branch to view its location:"
                    choices_list = []
                    for b in branches:
                        choices_list.append({
                            "title": b.name[:24],
                            "choice_id": f"loc_br_{b.id}",
                            "id": f"loc_br_{b.id}",
                            "button_id": f"loc_br_{b.id}",
                            "description": b.name[:72]
                        })
                    interactive_menu = {
                        "header_message": "",
                        "list_title": "Choose Branch",
                        "sections": [{"title": "Our Branches", "choices": choices_list}]
                    }
                else:
                    reply_text = "📍 No branch locations are currently available."
                    is_menu = False

            elif choice == "menu_contact" or "call" in choice or "contact" in choice:
                branches = company.branches.filter(is_deleted=False)
                if branches.count() == 1:
                    br = branches.first()
                    lines = [f"📞 *Contact Us: {br.name}*"]
                    if br.phone:
                        lines.append(f"Phone: {br.phone}")
                    if br.email:
                        lines.append(f"Email: {br.email}")
                    reply_text = "\n".join(lines)
                    if len(lines) == 1:
                        reply_text += "\nNo contact details available for this branch."
                    is_menu = False
                elif branches.count() > 1:
                    from core.functions import get_auto_id
                    ChatSession.objects.update_or_create(
                        phone_number=from_phone,
                        defaults={
                            'state': 'contact_select_branch',
                            'data': {},
                            'auto_id': get_auto_id(ChatSession)
                        }
                    )
                    reply_text = "Please select a branch to view its contact details:"
                    choices_list = []
                    for b in branches:
                        choices_list.append({
                            "title": b.name[:24],
                            "choice_id": f"contact_br_{b.id}",
                            "id": f"contact_br_{b.id}",
                            "button_id": f"contact_br_{b.id}",
                            "description": b.name[:72]
                        })
                    interactive_menu = {
                        "header_message": "",
                        "list_title": "Choose Branch",
                        "sections": [{"title": "Our Branches", "choices": choices_list}]
                    }
                else:
                    reply_text = "📞 No contact details are currently available."
                    is_menu = False
            else:
                # Default greeting + main menu
                booking_setting = BookingSettings.objects.filter(branch=branch).first()
                custom_welcome = booking_setting.whatsapp_welcome_message if booking_setting else None

                if custom_welcome:
                    cust_name = customer.name if customer else "Customer"
                    br_name = branch.name if branch else ""
                    comp_name = company.company_name if company else ""
                    reply_text = custom_welcome.replace("{customer_name}", cust_name)\
                                               .replace("{branch_name}", br_name)\
                                               .replace("{company_name}", comp_name)
                else:
                    if customer:
                        reply_text = f"Hi {customer.name}, Thank you for choosing {company.company_name}."
                    else:
                        reply_text = f"Thank you for contacting {company.company_name}."
                
                interactive_menu = {
                    "header_message": "",
                    "list_title": "Choose service",
                    "sections": [
                        {
                            "title": "Services",
                            "choices": [
                                { "title": "Schemes", "choice_id": "menu_schemes", "description": "" },
                                { "title": "Book an Appointment", "choice_id": "menu_book", "description": "" },
                                { "title": "Cancel Booking", "choice_id": "menu_cancel", "description": "" },
                                { "title": "Location", "choice_id": "menu_location", "description": "" },
                                { "title": "Contact Us", "choice_id": "menu_contact", "description": "" }
                            ]
                        }
                    ]
                }

            # 4. Send reply via wawy.org/Webgenie API
            try:
                with open('/tmp/wa_debug.log', 'a') as f:
                    f.write(f"BEFORE SEND: state='{getattr(session, 'state', 'NONE')}' choice='{choice}' reply='{reply_text}' loc={bool(location_pin)} menu={bool(interactive_menu)}\n")
            except Exception:
                pass
            response_text = send_whatsapp_simple(
                from_phone, 
                reply_text, 
                setting=setting, 
                interactive_data=interactive_menu,
                location_data=location_pin
            )
            status_str = 'Sent' if ('success' in response_text.lower() or 'wa_' in response_text.lower()) else 'Failed'

            # 5. Log the outgoing message safely
            safe_create_model(
                WhatsAppMessage,
                company=company,
                recipient_number=from_phone,
                message=reply_text,
                status=status_str
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


def get_user_branch_and_check_permission(user, branch_id):
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None
    from client_management.models import Branch
    
    if role == 'BRANCH_ADMIN':
        if not hasattr(user, 'managed_branch') or not user.managed_branch:
            return None, "Branch Admin has no managed branch assigned."
        return user.managed_branch, None
        
    elif role == 'COMPANY_ADMIN':
        if not branch_id:
            return None, "branch_id parameter is required for Company Admin."
        try:
            branch = Branch.objects.get(id=branch_id, company=user.profile.company, is_deleted=False)
            return branch, None
        except Branch.DoesNotExist:
            return None, "Invalid branch selected or branch does not belong to your company."
            
    return None, "Permission denied."


@csrf_exempt
def api_get_booking_settings(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    branch_id = request.GET.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    from booking_management.models import BookingSettings
    from core.functions import get_auto_id
    
    settings, created = BookingSettings.objects.get_or_create(
        branch=branch,
        defaults={
            'creator': user,
            'auto_id': get_auto_id(BookingSettings),
            'is_booking_enabled': True,
            'max_booking_per_day': 50
        }
    )
    
    closing_time_str = settings.booking_closing_time.strftime("%H:%M:%S") if settings.booking_closing_time else None
    
    return JsonResponse({
        'success': True,
        'booking_settings': {
            'is_booking_enabled': settings.is_booking_enabled,
            'max_booking_per_day': settings.max_booking_per_day,
            'booking_closing_time': closing_time_str,
            'whatsapp_welcome_message': settings.whatsapp_welcome_message,
            'whatsapp_ready_message': settings.whatsapp_ready_message,
            'whatsapp_thanks_message': settings.whatsapp_thanks_message,
        }
    })


@csrf_exempt
def api_update_booking_settings(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body'}, status=400)
        
    branch_id = body.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    from booking_management.models import BookingSettings
    
    is_booking_enabled = body.get('is_booking_enabled', True)
    max_booking_per_day = int(body.get('max_booking_per_day', 50))
    booking_closing_time = body.get('booking_closing_time')
    whatsapp_welcome_message = body.get('whatsapp_welcome_message')
    whatsapp_ready_message = body.get('whatsapp_ready_message')
    whatsapp_thanks_message = body.get('whatsapp_thanks_message')
    
    closing_time_obj = None
    if booking_closing_time:
        try:
            closing_time_obj = datetime.strptime(booking_closing_time, "%H:%M:%S").time()
        except ValueError:
            try:
                closing_time_obj = datetime.strptime(booking_closing_time, "%H:%M").time()
            except ValueError:
                return JsonResponse({'success': False, 'message': 'Invalid time format. Expected HH:MM:SS or HH:MM'}, status=400)
                
    settings, created = BookingSettings.objects.get_or_create(
        branch=branch,
        defaults={
            'creator': user,
            'auto_id': 0
        }
    )
    
    if created:
        from core.functions import get_auto_id
        settings.auto_id = get_auto_id(BookingSettings)
        
    settings.is_booking_enabled = is_booking_enabled
    settings.max_booking_per_day = max_booking_per_day
    settings.booking_closing_time = closing_time_obj
    settings.whatsapp_welcome_message = whatsapp_welcome_message
    settings.whatsapp_ready_message = whatsapp_ready_message
    settings.whatsapp_thanks_message = whatsapp_thanks_message
    settings.updater = user
    settings.save()
    
    return JsonResponse({'success': True, 'message': 'Booking settings updated successfully'})


@csrf_exempt
def api_holiday_list(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    branch_id = request.GET.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    from booking_management.models import HolidayCalendar
    holidays = HolidayCalendar.objects.filter(branch=branch, is_deleted=False).order_by('-holiday_date')
    
    return JsonResponse({
        'success': True,
        'holidays': [
            {
                'id': str(h.id),
                'holiday_date': h.holiday_date.strftime("%Y-%m-%d"),
                'repeat_yearly': h.repeat_yearly
            }
            for h in holidays
        ]
    })


@csrf_exempt
def api_holiday_create(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body'}, status=400)
        
    branch_id = body.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    holiday_date_str = body.get('holiday_date')
    if not holiday_date_str:
        return JsonResponse({'success': False, 'message': 'holiday_date is required'}, status=400)
        
    try:
        holiday_date = datetime.strptime(holiday_date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid date format. Expected YYYY-MM-DD'}, status=400)
        
    repeat_yearly = body.get('repeat_yearly', False)
    
    from booking_management.models import HolidayCalendar
    
    existing = HolidayCalendar.objects.filter(branch=branch, holiday_date=holiday_date).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.repeat_yearly = repeat_yearly
            existing.updater = user
            existing.save()
            return JsonResponse({'success': True, 'message': 'Holiday created successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Holiday already exists for this date'}, status=400)
            
    safe_create_model(
        HolidayCalendar,
        branch=branch,
        holiday_date=holiday_date,
        repeat_yearly=repeat_yearly,
        creator=user
    )
    
    return JsonResponse({'success': True, 'message': 'Holiday created successfully'})


@csrf_exempt
def api_holiday_delete(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body'}, status=400)
        
    holiday_id = body.get('id')
    if not holiday_id:
        return JsonResponse({'success': False, 'message': 'id is required'}, status=400)
        
    from booking_management.models import HolidayCalendar
    try:
        holiday = HolidayCalendar.objects.get(id=holiday_id, is_deleted=False)
        _, err = get_user_branch_and_check_permission(user, str(holiday.branch.id))
        if err:
            return JsonResponse({'success': False, 'message': 'Permission denied to delete this holiday'}, status=403)
            
        holiday.is_deleted = True
        holiday.updater = user
        holiday.save()
        
        return JsonResponse({'success': True, 'message': 'Holiday deleted successfully'})
    except HolidayCalendar.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Holiday not found'}, status=404)


@csrf_exempt
def api_weekly_off_list(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    branch_id = request.GET.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    from booking_management.models import WeeklyOffDay
    weekly_offs = WeeklyOffDay.objects.filter(branch=branch, is_deleted=False).order_by('day')
    
    return JsonResponse({
        'success': True,
        'weekly_offs': [
            {
                'id': str(w.id),
                'day': w.day
            }
            for w in weekly_offs
        ]
    })


@csrf_exempt
def api_weekly_off_create(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body'}, status=400)
        
    branch_id = body.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    day = body.get('day', '').lower().strip()
    from booking_management.models import WeeklyOffDay
    valid_days = [d[0] for d in WeeklyOffDay.DAYS]
    if day not in valid_days:
        return JsonResponse({'success': False, 'message': f'Invalid day. Must be one of: {", ".join(valid_days)}'}, status=400)
        
    existing = WeeklyOffDay.objects.filter(branch=branch, day=day).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.updater = user
            existing.save()
            return JsonResponse({'success': True, 'message': 'Weekly Off Day created successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Weekly Off Day already exists for this day'}, status=400)
            
    safe_create_model(
        WeeklyOffDay,
        branch=branch,
        day=day,
        creator=user
    )
    
    return JsonResponse({'success': True, 'message': 'Weekly Off Day created successfully'})


@csrf_exempt
def api_weekly_off_delete(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body'}, status=400)
        
    weekly_off_id = body.get('id')
    if not weekly_off_id:
        return JsonResponse({'success': False, 'message': 'id is required'}, status=400)
        
    from booking_management.models import WeeklyOffDay
    try:
        weekly_off = WeeklyOffDay.objects.get(id=weekly_off_id, is_deleted=False)
        _, err = get_user_branch_and_check_permission(user, str(weekly_off.branch.id))
        if err:
            return JsonResponse({'success': False, 'message': 'Permission denied to delete this weekly off day'}, status=403)
            
        weekly_off.is_deleted = True
        weekly_off.updater = user
        weekly_off.save()
        
        return JsonResponse({'success': True, 'message': 'Weekly Off Day deleted successfully'})
    except WeeklyOffDay.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Weekly Off Day not found'}, status=404)


@csrf_exempt
def api_booking_pause_list(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    branch_id = request.GET.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    from booking_management.models import BookingPause
    pauses = BookingPause.objects.filter(branch=branch, is_deleted=False).order_by('-from_date')
    
    return JsonResponse({
        'success': True,
        'pauses': [
            {
                'id': str(p.id),
                'from_date': p.from_date.strftime("%Y-%m-%d"),
                'to_date': p.to_date.strftime("%Y-%m-%d"),
                'reason': p.reason or ''
            }
            for p in pauses
        ]
    })


@csrf_exempt
def api_booking_pause_create(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body'}, status=400)
        
    branch_id = body.get('branch_id')
    branch, err = get_user_branch_and_check_permission(user, branch_id)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=403)
        
    from_date_str = body.get('from_date')
    to_date_str = body.get('to_date')
    reason = body.get('reason', '').strip()
    
    if not from_date_str or not to_date_str:
        return JsonResponse({'success': False, 'message': 'from_date and to_date are required'}, status=400)
        
    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid date format. Expected YYYY-MM-DD'}, status=400)
        
    if from_date > to_date:
        return JsonResponse({'success': False, 'message': 'from_date cannot be after to_date'}, status=400)
        
    from booking_management.models import BookingPause
    
    safe_create_model(
        BookingPause,
        branch=branch,
        from_date=from_date,
        to_date=to_date,
        reason=reason,
        creator=user
    )
    
    return JsonResponse({'success': True, 'message': 'Booking pause created successfully'})


@csrf_exempt
def api_booking_pause_delete(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON body'}, status=400)
        
    pause_id = body.get('id')
    if not pause_id:
        return JsonResponse({'success': False, 'message': 'id is required'}, status=400)
        
    from booking_management.models import BookingPause
    try:
        pause = BookingPause.objects.get(id=pause_id, is_deleted=False)
        _, err = get_user_branch_and_check_permission(user, str(pause.branch.id))
        if err:
            return JsonResponse({'success': False, 'message': 'Permission denied to delete this booking pause'}, status=403)
            
        pause.is_deleted = True
        pause.updater = user
        pause.save()
        
        return JsonResponse({'success': True, 'message': 'Booking pause deleted successfully'})
    except BookingPause.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Booking pause not found'}, status=404)


def send_booking_ready_alert_background(booking_id):
    from booking_management.models import Booking
    from client_management.models import WhatsAppSetting
    try:
        booking = Booking.objects.get(id=booking_id)
        customer = booking.customer
        if not customer:
            return
        
        # Resolve company WhatsAppSetting
        company = booking.branch.company if booking.branch else None
        if not company:
            return
            
        setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
        if not setting or not setting.username or not setting.password:
            return
            
        # Clean receiver phone number — strip non-digits and a leading 0 if present
        phone = customer.phone or customer.whatsapp_number or ""
        import re
        phone = re.sub(r'\D', '', phone)
        if phone.startswith('0'):
            phone = phone[1:]
            
        if not phone:
            return
            
        name = customer.name or "Customer"
        vehicle_number = booking.vehicle.vehicle_number if booking.vehicle else "your vehicle"
        
        branch_name = booking.branch.name if booking.branch else "Support"
        # Check if using the official/template API
        if setting.is_official_api:
            from booking_management.api_views import send_whatsapp_template
            # The 'ready1' template expects: {{1}} = Customer Name, {{2}} = Vehicle Number, {{3}} = Branch Name
            send_whatsapp_template(
                to_number=phone,
                template_name='ready1',
                values=[name, vehicle_number, branch_name],
                setting=setting
            )
        else:
            message = f"Hi {name} Great news! Your vehicle {vehicle_number} is ready for pickup. Please collect at your earliest convenience.\n{branch_name} Support team."
            from booking_management.api_views import send_whatsapp_simple
            send_whatsapp_simple(phone, message, setting=setting)
            
    except Exception as e:
        with open('/tmp/ready_alert_error.log', 'a') as f:
            f.write(f"Error sending ready alert: {e}\n")


@csrf_exempt
def api_send_ready_alert(request, booking_id):
    """Manually trigger the background Ready Alert WhatsApp notification for a booking."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        from booking_management.models import Booking
        booking = Booking.objects.get(id=booking_id, is_deleted=False)
        
        # Check if company WhatsAppSetting is configured
        company = booking.branch.company if booking.branch else None
        has_api = False
        if company:
            from client_management.models import WhatsAppSetting
            setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
            if setting and setting.username and setting.password:
                has_api = True

        if has_api:
            # Trigger ready alert automatically in background
            import threading
            threading.Thread(
                target=send_booking_ready_alert_background,
                args=(str(booking.id),),
                daemon=True
            ).start()
            
            return JsonResponse({
                'success': True,
                'action': 'auto',
                'message': 'Ready alert sent successfully via WhatsApp API'
            })
        else:
            return JsonResponse({
                'success': True,
                'action': 'manual',
                'message': 'WhatsApp API is not configured'
            })
            
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Booking not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_send_ready_alert_generic(request):
    """Trigger WhatsApp ready alert for a vehicle / customer without a specific booking."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        import json
        data = json.loads(request.body)
        phone = data.get('phone', '')
        vehicle_number = data.get('vehicle_number', '')
        customer_name = data.get('customer_name', 'Customer')
        
        # Resolve branch and company
        branch = getattr(user, 'managed_branch', None)
        company = user.profile.company if hasattr(user, 'profile') and user.profile else None
        if not company and branch and branch.company:
            company = branch.company

        if not company:
            return JsonResponse({'success': False, 'message': 'Company profile not found'}, status=400)

        branch_name = branch.name if branch else company.company_name
        company_name = company.company_name

        # Resolve custom message for this branch
        from booking_management.models import BookingSettings
        bs = BookingSettings.objects.filter(branch=branch).first() if branch else None
        default_msg = f"Hi {{customer_name}} Great news! Your vehicle {{vehicle_number}} is ready for pickup. Please collect at your earliest convenience.\n{{branch_name}} Support team."
        raw_template = (bs.whatsapp_ready_message if bs and bs.whatsapp_ready_message else default_msg)
        message = raw_template.replace('{customer_name}', customer_name) \
                               .replace('{vehicle_number}', vehicle_number) \
                               .replace('{branch_name}', branch_name) \
                               .replace('{company_name}', company_name)

        from client_management.models import WhatsAppSetting
        setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
        
        has_api = bool(setting and setting.username and setting.password)
            
        if has_api:
            import re
            cleaned_phone = re.sub(r'\D', '', phone)
            
            import threading
            if setting.is_official_api:
                from booking_management.api_views import send_whatsapp_template
                # Official Meta template: 'ready'
                threading.Thread(
                    target=send_whatsapp_template,
                    args=(cleaned_phone, 'ready', [customer_name, vehicle_number]),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()
            else:
                from booking_management.api_views import send_whatsapp_simple
                threading.Thread(
                    target=send_whatsapp_simple,
                    args=(cleaned_phone, message),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()
            
            return JsonResponse({
                'success': True,
                'action': 'auto',
                'message': 'Ready alert sent successfully via WhatsApp API'
            })
        else:
            return JsonResponse({
                'success': True,
                'action': 'manual',
                'message': 'WhatsApp API is not configured',
                'message_text': message,
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_send_welcome_msg_generic(request):
    """Trigger WhatsApp welcome message for a customer/vehicle."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        import json
        data = json.loads(request.body)
        phone = data.get('phone', '')
        vehicle_number = data.get('vehicle_number', '')
        customer_name = data.get('customer_name', 'Customer')
        
        # Resolve branch and company
        branch = getattr(user, 'managed_branch', None)
        company = user.profile.company if hasattr(user, 'profile') and user.profile else None

        # If managed_branch not set (e.g. non-staff BRANCH_ADMIN via app login),
        # look up the branch from the database using role
        if not branch:
            role = user.profile.role.name if hasattr(user, 'profile') and user.profile and user.profile.role else None
            if role == 'BRANCH_ADMIN':
                from client_management.models import Branch
                branch = Branch.objects.filter(
                    branch_admins=user, is_deleted=False
                ).first()
            if not branch and company:
                # Fallback: first branch of the company
                from client_management.models import Branch
                branch = Branch.objects.filter(company=company, is_deleted=False).first()

        if not company and branch and branch.company:
            company = branch.company

        if not company:
            return JsonResponse({'success': False, 'message': 'Company profile not found'}, status=400)

        branch_name = branch.name if branch else "our branch"
        company_name = company.company_name

        # Resolve custom message for this branch
        from booking_management.models import BookingSettings
        bs = BookingSettings.objects.filter(branch=branch).first() if branch else None
        default_msg = f"Hi {{customer_name}} Welcome to Our {{branch_name}}.Your vehicle {{vehicle_number}} has arrived safely and is in expert hands.We will keep you posted!"
        raw_template = (bs.whatsapp_welcome_message if bs and bs.whatsapp_welcome_message else default_msg)
        message = raw_template.replace('{customer_name}', customer_name) \
                               .replace('{vehicle_number}', vehicle_number) \
                               .replace('{branch_name}', branch_name) \
                               .replace('{company_name}', company_name)
                               
        # Resolve customer to get schemes
        from client_management.models import Customer
        customer = None
        if phone:
            import re
            cleaned_phone_digits = re.sub(r'\D', '', str(phone))
            if cleaned_phone_digits.startswith('0'):
                cleaned_phone_digits = cleaned_phone_digits[1:]
            customer = Customer.objects.filter(phone__contains=cleaned_phone_digits, company=company, is_deleted=False).first()
        if not customer and vehicle_number:
            from client_management.models import CustomerVehicle
            v_match = CustomerVehicle.objects.filter(vehicle_number__iexact=vehicle_number.replace(' ', ''), customer__company=company, is_deleted=False).first()
            if v_match:
                customer = v_match.customer
                
        if customer:
            from client_management.api_views import get_customer_available_schemes_message
            schemes_msg = get_customer_available_schemes_message(customer)
            if schemes_msg:
                message += schemes_msg

        from client_management.models import WhatsAppSetting
        setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
        
        has_api = bool(setting and setting.username and setting.password)
            
        if has_api:
            import re
            cleaned_phone = re.sub(r'\D', '', phone)
            
            import threading
            if setting.is_official_api:
                from booking_management.api_views import send_whatsapp_template
                # Official WAWY template 'welcome1': {{1}} = Customer Name, {{2}} = Branch Name, {{3}} = Vehicle Number
                threading.Thread(
                    target=send_whatsapp_template,
                    args=(cleaned_phone, 'welcome1', [customer_name, branch_name, vehicle_number]),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()
            else:
                from booking_management.api_views import send_whatsapp_simple
                threading.Thread(
                    target=send_whatsapp_simple,
                    args=(cleaned_phone, message),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()
            
            return JsonResponse({
                'success': True,
                'action': 'auto',
                'message': 'Welcome message sent successfully via WhatsApp API'
            })
        else:
            return JsonResponse({
                'success': True,
                'action': 'manual',
                'message': 'WhatsApp API is not configured',
                'message_text': message,
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_send_thanks_msg_generic(request):
    """Trigger WhatsApp thankful message for a customer/vehicle."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        import json
        data = json.loads(request.body)
        phone = data.get('phone', '')
        vehicle_number = data.get('vehicle_number', '')
        customer_name = data.get('customer_name', 'Customer')
        
        # Resolve branch and company
        branch = getattr(user, 'managed_branch', None)
        company = user.profile.company if hasattr(user, 'profile') and user.profile else None

        # If managed_branch not set (e.g. non-staff BRANCH_ADMIN via app login),
        # look up the branch from the database using role
        if not branch:
            role = user.profile.role.name if hasattr(user, 'profile') and user.profile and user.profile.role else None
            if role == 'BRANCH_ADMIN':
                from client_management.models import Branch
                branch = Branch.objects.filter(
                    branch_admins=user, is_deleted=False
                ).first()
            if not branch and company:
                # Fallback: first branch of the company
                from client_management.models import Branch
                branch = Branch.objects.filter(company=company, is_deleted=False).first()

        if not company and branch and branch.company:
            company = branch.company

        if not company:
            return JsonResponse({'success': False, 'message': 'Company profile not found'}, status=400)

        branch_name = branch.name if branch else "our branch"
        company_name = company.company_name

        # Resolve custom message for this branch
        from booking_management.models import BookingSettings
        bs = BookingSettings.objects.filter(branch=branch).first() if branch else None
        default_msg = f"Dear {{customer_name}} 🙏 Thank you for trusting us with your vehicle {{vehicle_number}}. We hope you had a great experience. Looking forward to seeing you again!\n{{branch_name}} support team."
        raw_template = (bs.whatsapp_thanks_message if bs and bs.whatsapp_thanks_message else default_msg)

        message = raw_template.replace('{customer_name}', customer_name) \
                               .replace('{vehicle_number}', vehicle_number) \
                               .replace('{branch_name}', branch_name) \
                               .replace('{company_name}', company_name)

        from client_management.models import WhatsAppSetting
        setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
        
        has_api = bool(setting and setting.username and setting.password)
            
        if has_api:
            import re
            cleaned_phone = re.sub(r'\D', '', phone)
            
            import threading
            if setting.is_official_api:
                from booking_management.api_views import send_whatsapp_template
                # Official Meta template: 'thanks'
                # Places: {{1}} = Customer Name, {{2}} = Vehicle Number, {{3}} = Branch Name
                threading.Thread(
                    target=send_whatsapp_template,
                    args=(cleaned_phone, 'thanks', [customer_name, vehicle_number, branch_name]),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()
            else:
                from booking_management.api_views import send_whatsapp_simple
                threading.Thread(
                    target=send_whatsapp_simple,
                    args=(cleaned_phone, message),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()
            
            return JsonResponse({
                'success': True,
                'action': 'auto',
                'message': 'Thank you message sent successfully via WhatsApp API'
            })
        else:
            return JsonResponse({
                'success': True,
                'action': 'manual',
                'message': 'WhatsApp API is not configured',
                'message_text': message,
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_reminder_list(request):
    """List scheduled reminder plans that are due or all active scheduled plans."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    from booking_management.models import ReminderPlan
    from django.utils import timezone
    from datetime import datetime

    # Get active date or show_all param
    date_str = request.GET.get('date')
    show_all = request.GET.get('show_all', '').lower() in ['true', '1', 'yes']
    all_dates = request.GET.get('all', '').lower() in ['true', '1', 'yes'] or date_str == 'all'
    lte_mode = request.GET.get('lte', '').lower() in ['true', '1', 'yes']
    
    selected_date = None
    if date_str and date_str.lower() not in ['all', 'today']:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    elif date_str and date_str.lower() == 'today':
        selected_date = timezone.now().date()
    elif not date_str and not show_all and not all_dates:
        selected_date = timezone.now().date()

    # Filter unsent and active plans
    plans = ReminderPlan.objects.filter(
        is_sent=False,
        is_deleted=False
    ).select_related(
        'invoice', 'invoice__customer', 'invoice__vehicle',
        'invoice__vehicle__vehicle_type_model', 'reminder', 'reminder__service', 'branch'
    ).order_by('scheduled_date')

    # If a specific date is provided and show_all is false, filter by selected_date
    if selected_date and not show_all and not all_dates:
        if lte_mode:
            plans = plans.filter(scheduled_date__lte=selected_date)
        else:
            plans = plans.filter(scheduled_date=selected_date)

    # Filter by user branch/company scope
    role = user.profile.role.name if (user.profile and user.profile.role) else None
    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        plans = plans.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and user.profile.company:
        plans = plans.filter(branch__company=user.profile.company)

    search_query = request.GET.get('search', '').strip()
    if search_query:
        from django.db.models import Q
        plans = plans.filter(
            Q(invoice__customer__name__icontains=search_query) |
            Q(invoice__customer__phone__icontains=search_query) |
            Q(invoice__customer__whatsapp_number__icontains=search_query) |
            Q(invoice__vehicle__vehicle_number__icontains=search_query)
        )

    plans_data = []
    for plan in plans:
        customer_name = plan.invoice.customer.name or "Customer"
        vehicle_no = plan.invoice.vehicle.vehicle_number if plan.invoice.vehicle else "your vehicle"

        # Resolve service item and service name accurately
        service_name = ""
        service_category = ""
        target_item = None

        if plan.reminder and plan.reminder.service:
            service_name = plan.reminder.service.name
            if plan.reminder.service.service_type:
                service_category = plan.reminder.service.service_type.slug
        elif plan.invoice:
            tmpl_name = (plan.template_name or '').lower()
            if tmpl_name == 'insurancereminder':
                target_item = next(
                    (it for it in plan.invoice.items.all() if (
                        (hasattr(it, 'service_detail') and it.service_detail and it.service_detail.service_category in ['auto_insurance', 'insurance']) or
                        (it.service and it.service.service_type and it.service.service_type.slug in ['auto_insurance', 'insurance']) or
                        'insurance' in (it.service_name or '').lower()
                    )),
                    None
                )
            elif tmpl_name == 'smoketest':
                target_item = next(
                    (it for it in plan.invoice.items.all() if (
                        (hasattr(it, 'service_detail') and it.service_detail and it.service_detail.service_category == 'smoke_test') or
                        (it.service and it.service.service_type and it.service.service_type.slug in ['smoke_test', 'pollution']) or
                        'smoke' in (it.service_name or '').lower() or 'pollution' in (it.service_name or '').lower()
                    )),
                    None
                )
            elif tmpl_name == 'oilreminder':
                target_item = next(
                    (it for it in plan.invoice.items.all() if (
                        (hasattr(it, 'service_detail') and it.service_detail and it.service_detail.service_category == 'oil_change') or
                        (it.service and it.service.service_type and it.service.service_type.slug == 'oil_change') or
                        'oil' in (it.service_name or '').lower()
                    )),
                    None
                )

            if target_item:
                service_name = target_item.service_name or (target_item.service.name if target_item.service else '')
                if hasattr(target_item, 'service_detail') and target_item.service_detail:
                    service_category = target_item.service_detail.service_category or ''
                elif target_item.service and target_item.service.service_type:
                    service_category = target_item.service.service_type.slug

            if not service_name:
                first_svc_item = plan.invoice.items.filter(stock_item__isnull=True).first() or plan.invoice.items.first()
                if first_svc_item:
                    service_name = first_svc_item.service_name or (first_svc_item.service.name if first_svc_item.service else '')
                    if hasattr(first_svc_item, 'service_detail') and first_svc_item.service_detail:
                        service_category = first_svc_item.service_detail.service_category or ''
                    elif first_svc_item.service and first_svc_item.service.service_type:
                        service_category = first_svc_item.service.service_type.slug

        if not service_name or service_name.lower() in ['insurancereminder', 'smoketest', 'oilreminder', 'servicesreminder', 'service reminder', 'reminder']:
            tmpl_name = (plan.template_name or '').lower()
            if tmpl_name == 'insurancereminder':
                service_name = 'Insurance'
                if not service_category:
                    service_category = 'auto_insurance'
            elif tmpl_name == 'smoketest':
                service_name = 'Smoke Test'
                if not service_category:
                    service_category = 'smoke_test'
            elif tmpl_name == 'oilreminder':
                service_name = 'Oil Change'
                if not service_category:
                    service_category = 'oil_change'
            else:
                service_name = 'Service'

        formatted_date = plan.scheduled_date.strftime("%d-%m-%Y") if plan.scheduled_date else ""
        
        next_oil_change_km = None
        next_alignment_km = None
        if plan.invoice:
            for item in plan.invoice.items.all():
                if hasattr(item, 'service_detail') and item.service_detail:
                    sd = item.service_detail
                    if sd.service_category == 'oil_change' or sd.next_oil_change_km:
                        if not service_category:
                            service_category = 'oil_change'
                        if sd.next_oil_change_km:
                            next_oil_change_km = sd.next_oil_change_km
                    elif sd.service_category in ['alignment', 'wheel_balancing'] or sd.next_alignment_km:
                        if not service_category:
                            service_category = 'alignment'
                        if sd.next_alignment_km:
                            next_alignment_km = str(sd.next_alignment_km)

        s_name_lower = service_name.lower()
        is_wheel = ('wheel' in s_name_lower or 'balance' in s_name_lower or 'alignment' in s_name_lower or service_category in ['alignment', 'wheel_balancing'])
        is_smoke = ('smoke' in s_name_lower or 'pollution' in s_name_lower or service_category == 'smoke_test' or plan.template_name == 'smoketest')

        if is_wheel:
            if not next_alignment_km and plan.invoice and plan.invoice.vehicle and plan.invoice.vehicle.next_alignment_km:
                next_alignment_km = str(plan.invoice.vehicle.next_alignment_km)

        formatted_smoke_due_date = formatted_date
        if is_smoke:
            smoke_due_date = None
            if plan.invoice:
                for item in plan.invoice.items.all():
                    if hasattr(item, 'service_detail') and item.service_detail and item.service_detail.next_smoke_test_date:
                        smoke_due_date = item.service_detail.next_smoke_test_date
                        break
            if not smoke_due_date and plan.invoice and plan.invoice.vehicle and plan.invoice.vehicle.next_smoke_test_date:
                smoke_due_date = plan.invoice.vehicle.next_smoke_test_date
            if not smoke_due_date and plan.scheduled_date:
                r_days = 15 if plan.reminder_no == 1 else 3
                if plan.invoice and plan.invoice.vehicle and plan.invoice.vehicle.vehicle_type_model and plan.invoice.vehicle.vehicle_type_model.emission_standard:
                    es = plan.invoice.vehicle.vehicle_type_model.emission_standard
                    r_days = es.reminder_1_days if plan.reminder_no == 1 else es.reminder_2_days
                smoke_due_date = plan.scheduled_date + timedelta(days=r_days)
            if smoke_due_date:
                formatted_smoke_due_date = smoke_due_date.strftime("%d-%m-%Y") if hasattr(smoke_due_date, 'strftime') else str(smoke_due_date)

        branch_name = ''
        if plan and plan.branch and plan.branch.name:
            branch_name = plan.branch.name.strip()
        elif plan and plan.invoice and plan.invoice.branch and plan.invoice.branch.name:
            branch_name = plan.invoice.branch.name.strip()
        elif plan and plan.invoice and plan.invoice.company and plan.invoice.company.company_name:
            branch_name = plan.invoice.company.company_name.strip()
        if not branch_name:
            branch_name = 'Mobiz Auto Care Pro'
        formatted_expiry = None

        if service_category == 'oil_change' or plan.template_name == 'oilreminder' or 'oil' in s_name_lower:
            message = f"Dear {customer_name} your vehicle no {vehicle_no} next oil change to be done on {next_oil_change_km or 'N/A'} km. Visit {branch_name} for a smooth ride."
        elif is_smoke:
            message = f"Hi {customer_name}, Your vehicle {vehicle_no}'s Smoke Test is due for renewal on {formatted_smoke_due_date}. Please visit {branch_name} to renew it before the due date."
        elif 'insurance' in s_name_lower or service_category in ['auto_insurance', 'insurance'] or plan.template_name == 'insurancereminder':
            if plan.invoice:
                for item in plan.invoice.items.all():
                    if hasattr(item, 'service_detail') and item.service_detail:
                        exp_val = getattr(item.service_detail, 'insurance_expiry_date', None)
                        if exp_val:
                            try:
                                if isinstance(exp_val, str):
                                    from datetime import datetime
                                    formatted_expiry = datetime.strptime(exp_val, "%Y-%m-%d").strftime("%d-%m-%Y")
                                else:
                                    formatted_expiry = exp_val.strftime("%d-%m-%Y")
                            except Exception:
                                pass
            if not formatted_expiry:
                formatted_expiry = (plan.invoice.date + timedelta(days=365)).strftime("%d-%m-%Y") if (plan.invoice and plan.invoice.date) else formatted_date

            ins_service_name = service_name if (service_name and service_name.lower() != 'service') else 'Insurance'
            if ins_service_name.lower().endswith(' policy'):
                ins_service_name = ins_service_name[:-7].strip()

            message = (
                f"Dear {customer_name}, {ins_service_name} policy expiry reminder.\n"
                f"Expiry date: {formatted_expiry}\n"
                f"Kindly contact for the renewal.\n"
                f"{branch_name} support team"
            )
        elif is_wheel:
            km_disp = f"{next_alignment_km} KM" if (next_alignment_km and str(next_alignment_km).upper() != 'N/A' and 'KM' not in str(next_alignment_km).upper()) else (next_alignment_km or 'N/A')
            if km_disp != 'N/A':
                message = f"Dear {customer_name}, your vehicle {vehicle_no} is due for Wheel Alignment at {km_disp}.\nVisit {branch_name} for a smooth ride."
            else:
                message = f"Dear {customer_name}, your vehicle {vehicle_no} is due for Wheel Alignment.\nVisit {branch_name} for a smooth ride."
        else:
            msg_template = (plan.reminder.reminder_message if (plan.reminder and plan.reminder.reminder_message) else "").strip()
            if not msg_template:
                msg_template = "Dear {customer_name}, your vehicle {vehicle_number} is scheduled for {service_name} reminder on {scheduled_date}."
            if msg_template.startswith('"') and msg_template.endswith('"'):
                msg_template = msg_template[1:-1].strip()

            message = msg_template.replace('{customer_name}', customer_name) \
                                   .replace('{vehicle_number}', vehicle_no) \
                                   .replace('{service_name}', service_name) \
                                   .replace('{expiry_date}', formatted_date) \
                                   .replace('{scheduled_date}', formatted_date) \
                                   .replace('{due_date}', formatted_date) \
                                   .replace('{next_date}', formatted_date)

            if 'expired on ' in message and service_name and service_name in message:
                message = message.replace(f"expired on {service_name}", f"expired on {formatted_date}")

        plans_data.append({
            'id': str(plan.id),
            'customer_name': customer_name,
            'customer_phone': plan.invoice.customer.phone or plan.invoice.customer.whatsapp_number or "",
            'vehicle_number': vehicle_no,
            'vehicle_type': plan.invoice.vehicle.vehicle_type_model.name if (plan.invoice.vehicle and plan.invoice.vehicle.vehicle_type_model) else "N/A",
            'reminder_no': plan.reminder_no,
            'service_name': service_name,
            'service_category': service_category,
            'branch_name': branch_name,
            'next_oil_change_km': next_oil_change_km,
            'scheduled_date': str(plan.scheduled_date),
            'formatted_date': formatted_date,
            'formatted_expiry': formatted_expiry,
            'smoke_due_date': formatted_smoke_due_date,
            'due_date': formatted_smoke_due_date if is_smoke else (formatted_expiry if 'insurance' in s_name_lower or service_category in ['auto_insurance', 'insurance'] or plan.template_name == 'insurancereminder' else formatted_date),
            'message': message,
        })

    return JsonResponse({
        'success': True,
        'plans': plans_data,
        'selected_date': str(selected_date) if selected_date else "",
    })


@csrf_exempt
def api_send_reminder(request):
    """Trigger reminder sending for a list of ReminderPlan IDs."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        plan_ids = data.get('plan_ids', [])
        action = data.get('action')

        from booking_management.models import ReminderPlan, SentServiceReminder
        from client_management.models import WhatsAppSetting
        from booking_management.api_views import send_whatsapp_simple, send_whatsapp_template
        import re
        import urllib.parse

        # Action: Mark Sent (used after manual fallback)
        if action == 'mark_sent':
            for p_id in plan_ids:
                try:
                    plan = ReminderPlan.objects.get(id=p_id, is_deleted=False, is_sent=False)
                    plan.is_sent = True
                    plan.save()
                    SentServiceReminder.objects.get_or_create(
                        reminder=plan.reminder,
                        invoice=plan.invoice
                    )
                except ReminderPlan.DoesNotExist:
                    pass
            return JsonResponse({'success': True, 'message': 'Marked as sent'})

        sent_count = 0

        for p_id in plan_ids:
            try:
                plan = ReminderPlan.objects.get(id=p_id, is_deleted=False, is_sent=False)
            except ReminderPlan.DoesNotExist:
                continue

            reminder = plan.reminder
            invoice = plan.invoice

            # Fetch setting
            company = plan.branch.company if plan.branch else None
            setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()

            # Prepare phone number & fallback link
            phone = invoice.customer.phone or invoice.customer.whatsapp_number
            cleaned_phone = ""
            if phone:
                cleaned_phone = re.sub(r'\D', '', str(phone))
                if cleaned_phone.startswith('0'):
                    cleaned_phone = cleaned_phone[1:]

            customer_name = invoice.customer.name or "Customer"
            vehicle_no = invoice.vehicle.vehicle_number if invoice.vehicle else "your vehicle"
            formatted_date = plan.scheduled_date.strftime("%d-%m-%Y") if plan.scheduled_date else ""

            first_item = invoice.items.filter(service__isnull=False).first() if invoice else None
            if reminder and reminder.service:
                service_name = reminder.service.name
            elif first_item:
                service_name = first_item.service_name or (first_item.service.name if first_item.service else '')
            else:
                service_name = plan.template_name or "Service Reminder"

            # Prefilled message (Template text fallback)
            msg_template = (reminder.reminder_message if (reminder and reminder.reminder_message) else "").strip()
            if not msg_template:
                msg_template = "Dear {customer_name}, your vehicle {vehicle_number} is scheduled for {service_name} reminder on {scheduled_date}."
            if msg_template.startswith('"') and msg_template.endswith('"'):
                msg_template = msg_template[1:-1].strip()

            message = msg_template.replace('{customer_name}', customer_name) \
                                   .replace('{vehicle_number}', vehicle_no) \
                                   .replace('{service_name}', service_name) \
                                   .replace('{expiry_date}', formatted_date) \
                                   .replace('{scheduled_date}', formatted_date) \
                                   .replace('{due_date}', formatted_date) \
                                   .replace('{next_date}', formatted_date)

            if 'expired on ' in message and service_name and service_name in message:
                message = message.replace(f"expired on {service_name}", f"expired on {formatted_date}")

            encoded_message = urllib.parse.quote(message)
            fallback_url = f"https://api.whatsapp.com/send?phone={cleaned_phone}&text={encoded_message}"

            # Check if this is an oil change, smoke test, or wheel balancing/alignment reminder
            is_oil = False
            is_smoke = False
            is_wheel = False
            next_km = ""

            s_name_lower = service_name.lower()
            if 'wheel' in s_name_lower or 'balance' in s_name_lower or 'alignment' in s_name_lower:
                is_wheel = True
            elif 'smoke' in s_name_lower or 'pollution' in s_name_lower:
                is_smoke = True
            elif 'oil' in s_name_lower:
                is_oil = True

            if reminder and reminder.service:
                cat_slug = reminder.service.service_type.slug if reminder.service.service_type else ""
                if cat_slug == 'oil_change':
                    is_oil = True
                elif cat_slug == 'smoke_test':
                    is_smoke = True
                elif cat_slug in ['wheel_balancing', 'alignment']:
                    is_wheel = True

            for item in invoice.items.all():
                if hasattr(item, 'service_detail') and item.service_detail:
                    sd = item.service_detail
                    if sd.service_category == 'oil_change' or sd.next_oil_change_km:
                        is_oil = True
                        if sd.next_oil_change_km:
                            next_km = str(sd.next_oil_change_km)
                    elif sd.service_category in ['alignment', 'wheel_balancing']:
                        is_wheel = True

            branch_name = ''
            if plan and plan.branch and plan.branch.name:
                branch_name = plan.branch.name.strip()
            elif invoice and invoice.branch and invoice.branch.name:
                branch_name = invoice.branch.name.strip()
            elif invoice and invoice.company and invoice.company.company_name:
                branch_name = invoice.company.company_name.strip()
            if not branch_name:
                branch_name = 'Mobiz Auto Care Pro'

            if is_oil:
                tmpl_name = 'oilreminder'
                tmpl_values = [customer_name, vehicle_no, next_km or "N/A"]
                message = f"Dear {customer_name} your vehicle no {vehicle_no} next oil change to be done on {next_km or 'N/A'} km. Visit {branch_name} for a smooth ride."
            elif 'insurance' in s_name_lower or (reminder and reminder.service and reminder.service.service_type and 'insurance' in reminder.service.service_type.slug) or plan.template_name == 'insurancereminder':
                tmpl_name = 'insurancereminder'
                formatted_expiry = None
                if invoice:
                    for item in invoice.items.all():
                        if hasattr(item, 'service_detail') and item.service_detail:
                            exp_val = getattr(item.service_detail, 'insurance_expiry_date', None)
                            if exp_val:
                                try:
                                    if isinstance(exp_val, str):
                                        from datetime import datetime
                                        formatted_expiry = datetime.strptime(exp_val, "%Y-%m-%d").strftime("%d-%m-%Y")
                                    else:
                                        formatted_expiry = exp_val.strftime("%d-%m-%Y")
                                except Exception:
                                    pass
                if not formatted_expiry:
                    formatted_expiry = (invoice.date + timedelta(days=365)).strftime("%d-%m-%Y") if (invoice and invoice.date) else formatted_date

                ins_service_name = service_name if (service_name and service_name.lower() != 'service') else 'Insurance'
                if ins_service_name.lower().endswith(' policy'):
                    ins_service_name = ins_service_name[:-7].strip()

                tmpl_values = [customer_name, ins_service_name, formatted_expiry, branch_name]
                message = (
                    f"Dear {customer_name}, {ins_service_name} policy expiry reminder.\n"
                    f"Expiry date: {formatted_expiry}\n"
                    f"Kindly contact for the renewal.\n"
                    f"{branch_name} support team"
                )
            elif is_smoke:
                tmpl_name = (plan.template_name or (reminder.template_name if reminder else 'smoketest')).strip()
                smoke_due_date = None
                if invoice:
                    for item in invoice.items.all():
                        if hasattr(item, 'service_detail') and item.service_detail and item.service_detail.next_smoke_test_date:
                            smoke_due_date = item.service_detail.next_smoke_test_date
                            break
                if not smoke_due_date and invoice and invoice.vehicle and invoice.vehicle.next_smoke_test_date:
                    smoke_due_date = invoice.vehicle.next_smoke_test_date
                if not smoke_due_date and plan.scheduled_date:
                    r_days = 15 if plan.reminder_no == 1 else 3
                    if invoice and invoice.vehicle and invoice.vehicle.vehicle_type_model and invoice.vehicle.vehicle_type_model.emission_standard:
                        es = invoice.vehicle.vehicle_type_model.emission_standard
                        r_days = es.reminder_1_days if plan.reminder_no == 1 else es.reminder_2_days
                    smoke_due_date = plan.scheduled_date + timedelta(days=r_days)
                formatted_smoke_due_date = smoke_due_date.strftime("%d-%m-%Y") if (smoke_due_date and hasattr(smoke_due_date, 'strftime')) else formatted_date
                tmpl_values = [customer_name, vehicle_no, formatted_smoke_due_date, branch_name]
                message = f"Hi {customer_name}, Your vehicle {vehicle_no}'s Smoke Test is due for renewal on {formatted_smoke_due_date}. Please visit {branch_name} to renew it before the due date."
            elif is_wheel:
                # Always force 'wheelalignment' template for wheel alignment/balancing services.
                # DB stores 'servicereminder' as default — never use that for wheel services.
                tmpl_name = 'wheelalignment'
                # wheelalignment Wawy template: {{1}}=customer_name, {{2}}=vehicle_no, {{3}}=next_alignment_km, {{4}}=branch_name
                branch_name = ''
                if plan and plan.branch and plan.branch.name:
                    branch_name = plan.branch.name.strip()
                elif invoice and invoice.branch and invoice.branch.name:
                    branch_name = invoice.branch.name.strip()
                elif invoice and invoice.company and invoice.company.company_name:
                    branch_name = invoice.company.company_name.strip()
                if not branch_name:
                    branch_name = 'Mobiz Auto Care Pro'
                # Resolve next alignment KM from invoice service_detail or vehicle
                next_alignment_km = 'N/A'
                if invoice:
                    for _item in invoice.items.all():
                        if hasattr(_item, 'service_detail') and _item.service_detail and _item.service_detail.next_alignment_km:
                            next_alignment_km = str(_item.service_detail.next_alignment_km)
                            break
                    if next_alignment_km == 'N/A' and invoice.vehicle and invoice.vehicle.next_alignment_km:
                        next_alignment_km = str(invoice.vehicle.next_alignment_km)
                tmpl_values = [customer_name, vehicle_no, next_alignment_km, branch_name]

                km_disp = f"{next_alignment_km} KM" if (next_alignment_km and str(next_alignment_km).upper() != 'N/A' and 'KM' not in str(next_alignment_km).upper()) else (next_alignment_km or 'N/A')
                if km_disp != 'N/A':
                    message = f"Dear {customer_name}, your vehicle {vehicle_no} is due for Wheel Alignment at {km_disp}.\nVisit {branch_name} for a smooth ride."
                else:
                    message = f"Dear {customer_name}, your vehicle {vehicle_no} is due for Wheel Alignment.\nVisit {branch_name} for a smooth ride."
            else:
                tmpl_name = (plan.template_name or (reminder.template_name if reminder else 'servicesreminder')).strip()
                if tmpl_name.lower() in ['servicereminder', 'reminderservice']:
                    tmpl_name = 'servicesreminder'
                tmpl_values = [customer_name, vehicle_no, service_name]

            encoded_message = urllib.parse.quote(message)
            fallback_url = f"https://api.whatsapp.com/send?phone={cleaned_phone}&text={encoded_message}"

            # Check if API is available
            if not setting or not setting.username or not setting.password:
                if len(plan_ids) == 1:
                    # Return fallback prefill link directly
                    return JsonResponse({
                        'success': False,
                        'use_fallback': True,
                        'whatsapp_url': fallback_url,
                        'plan_id': plan.id,
                        'message': 'WhatsApp API not configured. Use manual sending.'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'WhatsApp API is not configured. Send individually to use manual prefill.'
                    })

            # Send via API
            # Always use template API for official templates (wheel, oil, smoke, reminderservice)
            use_template = True
            try:
                if use_template:
                    send_whatsapp_template(
                        to_number=cleaned_phone,
                        template_name=tmpl_name,
                        values=tmpl_values,
                        setting=setting
                    )
                else:
                    send_whatsapp_simple(
                        to_number=cleaned_phone,
                        message=message,
                        setting=setting
                    )
            except Exception as api_err:
                # If single send fails, try manual fallback
                if len(plan_ids) == 1:
                    return JsonResponse({
                        'success': False,
                        'use_fallback': True,
                        'whatsapp_url': fallback_url,
                        'plan_id': plan.id,
                        'message': f'API Error: {str(api_err)}. Switch to manual fallback.'
                    })
                else:
                    continue

            # Mark sent
            plan.is_sent = True
            plan.save()

            # Log sent reminder for reports/compatibility
            if reminder:
                SentServiceReminder.objects.get_or_create(
                    reminder=reminder,
                    invoice=invoice
                )
            sent_count += 1

        return JsonResponse({'success': True, 'sent_count': sent_count})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
def api_send_oil_reminder(request):
    """Trigger WhatsApp oil service reminder (template: 'oilreminder').
    Template parameters:
      {{1}} = Customer Name
      {{2}} = Vehicle Number
      {{3}} = Next Oil Change KM
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        phone = data.get('phone', '')
        customer_name = data.get('customer_name', 'Customer')
        vehicle_number = data.get('vehicle_number', 'your vehicle')
        next_oil_change_km = str(data.get('next_oil_change_km') or data.get('next_km') or 'N/A')

        # Clean phone
        import re
        cleaned_phone = re.sub(r'\D', '', str(phone))
        if cleaned_phone.startswith('0'):
            cleaned_phone = cleaned_phone[1:]

        # Resolve branch & company
        branch = getattr(user, 'managed_branch', None)
        company = user.profile.company if hasattr(user, 'profile') and user.profile else None
        if not company and branch and branch.company:
            company = branch.company

        if not company:
            return JsonResponse({'success': False, 'message': 'Company profile not found'}, status=400)

        from client_management.models import WhatsAppSetting
        setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()

        branch_name = ''
        if branch and branch.name:
            branch_name = branch.name.strip()
        elif company and company.company_name:
            branch_name = company.company_name.strip()
        if not branch_name:
            branch_name = 'Mobiz Auto Care Pro'

        message_text = f"Dear {customer_name} your vehicle no {vehicle_number} next oil change to be done on {next_oil_change_km} km. Visit {branch_name} for a smooth ride."
        import urllib.parse
        encoded_msg = urllib.parse.quote(message_text)
        whatsapp_url = f"https://api.whatsapp.com/send?phone={cleaned_phone}&text={encoded_msg}"

        has_api = bool(setting and setting.username and setting.password)

        if has_api and cleaned_phone:
            import threading
            if setting.is_official_api:
                # Meta official WABA template: 'oilreminder'
                # {{1}} = customer_name, {{2}} = vehicle_number, {{3}} = next_oil_change_km
                threading.Thread(
                    target=send_whatsapp_template,
                    args=(cleaned_phone, 'oilreminder', [customer_name, vehicle_number, next_oil_change_km]),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()
            else:
                threading.Thread(
                    target=send_whatsapp_simple,
                    args=(cleaned_phone, message_text),
                    kwargs={'setting': setting},
                    daemon=True
                ).start()

            return JsonResponse({
                'success': True,
                'action': 'auto',
                'message': 'Oil service reminder sent successfully via WhatsApp API',
                'whatsapp_url': whatsapp_url
            })
        else:
            return JsonResponse({
                'success': True,
                'action': 'manual',
                'message': 'WhatsApp API is not configured',
                'message_text': message_text,
                'whatsapp_url': whatsapp_url
            })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# JOB CARD / JOB ORDER APIS – MOBIZ AUTO CARE PRO
# ══════════════════════════════════════════════════════════════════════════════
from .models import JobCard, JobCardServiceItem, JobCardPartItem, JobCardLabourItem, JobCardExtraItem
from client_management.models import Customer, CustomerVehicle, Branch, Stock, CustomerType
from master.models import VehicleMake, VehicleBrandModel, VehicleTypeModel, VehicleColor, EmissionStandard, VehicleType
from service_management.models import Service, ServiceVehicleTypePrice, BranchService
from tax_management.models import CompanyTax
from core.functions import get_auto_id
from django.db import transaction
from decimal import Decimal


@csrf_exempt
def api_job_card_list(request):
    """
    Returns list of job cards with filtering by tab:
    all, new, delayed, history, completed
    and search by job_number, vehicle_number, customer name or phone.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    company = getattr(getattr(user, 'profile', None), 'company', None)
    role = getattr(user.profile.role, 'name', None) if hasattr(user, 'profile') and user.profile and user.profile.role else None

    qs = JobCard.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__make', 'vehicle__brand_model', 
        'vehicle__vehicle_type_model', 'vehicle__vehicle_type_model__vehicle_type',
        'branch', 'quotation', 'job_quotation'
    )

    if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
        qs = qs.filter(branch=user.managed_branch)
    elif role == 'COMPANY_ADMIN' and company:
        qs = qs.filter(company=company)
    elif company:
        qs = qs.filter(company=company)

    # Filter by tab
    tab = request.GET.get('tab', 'all').lower().strip()
    now = timezone.now()
    if tab == 'new':
        qs = qs.filter(status=JobCard.STATUS_NEW)
    elif tab == 'delayed':
        qs = qs.filter(
            Q(status=JobCard.STATUS_DELAYED) | 
            (Q(expected_delivery_date__lt=now) & ~Q(status__in=[JobCard.STATUS_COMPLETED, JobCard.STATUS_CANCELLED]))
        )
    elif tab == 'completed':
        qs = qs.filter(status=JobCard.STATUS_COMPLETED)
    elif tab == 'history':
        qs = qs.filter(status__in=[JobCard.STATUS_COMPLETED, JobCard.STATUS_CANCELLED])

    # Search filter
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(job_number__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(customer__phone__icontains=search)
        )

    job_cards_data = []
    for jc in qs.order_by('-date_added'):
        v = jc.vehicle
        v_type = v.vehicle_type_model.vehicle_type.name if (v and v.vehicle_type_model and v.vehicle_type_model.vehicle_type) else ''
        v_make = v.make.name if (v and v.make) else ''
        v_model = (v.brand_model.name if (v and v.brand_model) else '') or (v.vehicle_type_model.name if (v and v.vehicle_type_model) else '')
        
        effective_status = jc.status
        if jc.status not in (JobCard.STATUS_COMPLETED, JobCard.STATUS_CANCELLED) and jc.expected_delivery_date and jc.expected_delivery_date < now:
            effective_status = JobCard.STATUS_DELAYED

        job_cards_data.append({
            'id': str(jc.id),
            'job_number': jc.job_number,
            'job_date': jc.job_date.strftime('%d-%m-%Y') if jc.job_date else '',
            'vehicle_id': str(v.id) if v else '',
            'vehicle_number': v.vehicle_number if v else '',
            'customer_id': str(jc.customer.id),
            'customer_name': jc.customer.name,
            'customer_phone': jc.customer.phone,
            'customer_whatsapp': jc.customer.whatsapp_number or jc.customer.phone,
            'delivery_date': jc.expected_delivery_date.strftime('%d-%m-%Y %I:%M %p') if jc.expected_delivery_date else '',
            'delivery_lead_time': jc.delivery_lead_time or '',
            'estimated_cost': float(jc.estimated_cost or 0),
            'quotation_id': str(jc.quotation_id or jc.job_quotation_id or ''),
            'quotation_number': jc.quotation.quotation_number if jc.quotation_id else (jc.job_quotation.quotation_number if jc.job_quotation_id else ''),
            'job_quotation_id': str(jc.job_quotation_id or ''),
            'vehicle_type': v_type,
            'vehicle_make': v_make,
            'vehicle_model': v_model,
            'vehicle_segment': v.segment if v else '',
            'current_section': jc.current_section or 'General Inspection',
            'current_service': jc.current_service or '',
            'status': effective_status,
            'status_display': dict(JobCard.STATUS_CHOICES).get(effective_status, effective_status.title()),
        })

    return JsonResponse({
        'success': True,
        'count': len(job_cards_data),
        'job_cards': job_cards_data,
    })


@csrf_exempt
def api_job_card_detail(request, job_card_id):
    """Returns complete details of a specific job card."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        jc = JobCard.objects.select_related(
            'customer', 'customer__customer_type', 'vehicle', 'vehicle__make',
            'vehicle__brand_model', 'vehicle__vehicle_type_model',
            'vehicle__vehicle_type_model__vehicle_type', 'vehicle__color',
            'vehicle__emission_standard', 'branch', 'company', 'quotation', 'job_quotation'
        ).get(id=job_card_id, is_deleted=False)
    except JobCard.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Job Card not found'}, status=404)

    c = jc.customer
    v = jc.vehicle
    now = timezone.now()
    effective_status = jc.status
    if jc.status not in (JobCard.STATUS_COMPLETED, JobCard.STATUS_CANCELLED) and jc.expected_delivery_date and jc.expected_delivery_date < now:
        effective_status = JobCard.STATUS_DELAYED

    services_list = []
    for s in jc.service_items.filter(is_deleted=False):
        services_list.append({
            'id': str(s.id),
            'service_id': str(s.service.id) if s.service else '',
            'service_name': s.service_name,
            'quantity': float(s.quantity or 1),
            'unit': s.unit or 'Unit',
            'rate': float(s.rate or 0),
            'discount': float(s.discount or 0),
            'vat_percentage': float(s.vat_percentage or 0),
            'total_amount': float(s.total_amount or 0),
            'warranty': s.warranty or '',
            'warranty_period': s.warranty_period or '',
            'remarks': s.remarks or '',
        })

    parts_list = []
    for p in jc.part_items.filter(is_deleted=False):
        parts_list.append({
            'id': str(p.id),
            'stock_item_id': str(p.stock_item.id) if p.stock_item else '',
            'part_number': p.part_number or '',
            'alternate_part_number': p.alternate_part_number or '',
            'product_code': p.product_code or '',
            'product_name': p.product_name,
            'current_stock': float(p.current_stock or 0),
            'unit': p.unit or 'Pcs',
            'rate': float(p.rate or 0),
            'rate_with_tax': float(p.rate_with_tax or 0),
            'quantity': float(p.quantity or 1),
            'discount': float(p.discount or 0),
            'vat_percentage': float(p.vat_percentage or 0),
            'total_amount': float(p.total_amount or 0),
            'remarks': p.remarks or '',
        })

    labour_list = []
    for l in jc.labour_items.filter(is_deleted=False):
        labour_list.append({
            'id': str(l.id),
            'labour_particulars': l.labour_particulars,
            'quantity': float(l.quantity or 1),
            'rate': float(l.rate or 0),
            'discount': float(l.discount or 0),
            'vat_percentage': float(l.vat_percentage or 0),
            'total_amount': float(l.total_amount or 0),
            'remarks': l.remarks or '',
        })

    extras_list = []
    for e in jc.extra_items.filter(is_deleted=False):
        extras_list.append({
            'id': str(e.id),
            'extra_details': e.extra_details,
            'quantity': float(e.quantity or 1),
            'rate': float(e.rate or 0),
            'discount': float(e.discount or 0),
            'discount_type': e.discount_type or 'amount',
            'discount_percentage': float(e.discount_percentage or 0),
            'vat_percentage': float(e.vat_percentage or 0),
            'total_amount': float(e.total_amount or 0),
            'remarks': e.remarks or '',
        })

    eff_es = v.emission_standard or (v.vehicle_type_model.emission_standard if (v and v.vehicle_type_model) else None)

    company = jc.company or (jc.branch.company if jc.branch else None)
    company_name = getattr(company, 'company_name', None) or getattr(company, 'name', '')
    company_logo_url = ''
    if company:
        logo_f = getattr(company, 'logo_color', None) or getattr(company, 'logo_bw', None) or getattr(company, 'logo', None)
        if logo_f:
            try:
                company_logo_url = request.build_absolute_uri(logo_f.url)
            except Exception:
                company_logo_url = logo_f.url if hasattr(logo_f, 'url') else ''
    if not company_logo_url and jc.branch and getattr(jc.branch, 'logo', None):
        try:
            company_logo_url = request.build_absolute_uri(jc.branch.logo.url)
        except Exception:
            company_logo_url = jc.branch.logo.url if hasattr(jc.branch.logo, 'url') else ''

    return JsonResponse({
        'success': True,
        'job_card': {
            'id': str(jc.id),
            'job_number': jc.job_number,
            'job_date': jc.job_date.strftime('%d-%m-%Y') if jc.job_date else '',
            'expected_delivery_date': jc.expected_delivery_date.strftime('%d-%m-%Y %I:%M %p') if jc.expected_delivery_date else '',
            'delivery_lead_time': jc.delivery_lead_time or '',
            'estimated_cost': float(jc.estimated_cost or 0),
            'current_section': jc.current_section or 'General Inspection',
            'current_service': jc.current_service or '',
            'status': effective_status,
            'status_display': dict(JobCard.STATUS_CHOICES).get(effective_status, effective_status.title()),
            'additional_remarks': jc.additional_remarks or '',
            'appointment_details': jc.appointment_details or '',
            'branch_name': jc.branch.name if jc.branch else '',
            'company_name': company_name,
            'company_logo': company_logo_url,
            'customer': {
                'id': str(c.id),
                'name': c.name,
                'phone': c.phone,
                'whatsapp': c.whatsapp_number or '',
                'email': c.email or '',
                'address': c.address or '',
                'city': c.city or '',
                'state': c.state or '',
                'country': c.country or '',
                'customer_type': c.customer_type.name if c.customer_type else 'Individual',
                'tax_number': c.tax_number or '',
                'tin_number': c.tin_number or '',
            },
            'vehicle': {
                'id': str(v.id) if v else '',
                'vehicle_number': v.vehicle_number if v else '',
                'chassis_number': v.chassis_number or '',
                'engine_number': v.engine_number or '',
                'make': v.make.name if (v and v.make) else '',
                'make_id': str(v.make.id) if (v and v.make) else '',
                'model': (v.brand_model.name if (v and v.brand_model) else '') or (v.vehicle_type_model.name if (v and v.vehicle_type_model) else ''),
                'brand_model_id': str(v.brand_model.id) if (v and v.brand_model) else '',
                'vehicle_type': v.vehicle_type_model.vehicle_type.name if (v and v.vehicle_type_model and v.vehicle_type_model.vehicle_type) else '',
                'vehicle_type_id': str(v.vehicle_type_model.vehicle_type.id) if (v and v.vehicle_type_model and v.vehicle_type_model.vehicle_type) else '',
                'model_year': v.model_year or '',
                'variant_trim': v.variant_trim or '',
                'color': v.color.name if (v and v.color) else '',
                'color_id': str(v.color.id) if (v and v.color) else '',
                'segment': v.segment or (v.vehicle_type_model.name if (v and v.vehicle_type_model) else ''),
                'transmission_type': v.transmission_type or '',
                'fuel_type': v.fuel_type or '',
                'wheel_type': v.wheel_type or 'normal_wheel',
                'current_odometer_km': getattr(v, 'current_odometer_km', None) or 0,
                'emission_standard': eff_es.name if eff_es else '',
                'emission_standard_id': str(eff_es.id) if eff_es else '',
            },
            'services': services_list,
            'parts': parts_list,
            'labour': labour_list,
            'extras': extras_list,
            'quotation_id': str(jc.quotation_id or jc.job_quotation_id or ''),
            'quotation_number': jc.quotation.quotation_number if jc.quotation_id else (jc.job_quotation.quotation_number if jc.job_quotation_id else ''),
            'job_quotation_id': str(jc.job_quotation_id or ''),
        }
    })


@csrf_exempt
def api_job_card_create(request):
    """Creates a new job card with services, parts, labour, extras."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        vehicle_id = data.get('vehicle_id')

        if not customer_id or not vehicle_id:
            return JsonResponse({'success': False, 'message': 'Customer and Vehicle are required'}, status=400)

        customer = Customer.objects.get(id=customer_id, is_deleted=False)
        vehicle = CustomerVehicle.objects.get(id=vehicle_id, customer=customer, is_deleted=False)

        company = user.profile.company if hasattr(user, 'profile') and user.profile and user.profile.company else customer.company
        branch = None
        role = getattr(user.profile.role, 'name', None) if hasattr(user, 'profile') and user.profile and user.profile.role else None
        if role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch') and user.managed_branch:
            branch = user.managed_branch
        elif data.get('branch_id'):
            branch = Branch.objects.filter(id=data.get('branch_id'), is_deleted=False).first()
        if not branch:
            branch = customer.branch

        # Parse delivery date
        expected_delivery = None
        delivery_date_str = data.get('expected_delivery_date')
        if delivery_date_str:
            for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %I:%M %p', '%Y-%m-%d', '%d-%m-%Y %H:%M', '%d-%m-%Y'):
                try:
                    expected_delivery = datetime.strptime(delivery_date_str, fmt)
                    if timezone.is_naive(expected_delivery):
                        expected_delivery = timezone.make_aware(expected_delivery)
                    break
                except ValueError:
                    pass

        with transaction.atomic():
            jc = JobCard.objects.create(
                company=company,
                branch=branch,
                customer=customer,
                vehicle=vehicle,
                expected_delivery_date=expected_delivery,
                delivery_lead_time=data.get('delivery_lead_time', '').strip() or None,
                current_section=data.get('current_section', 'General Inspection').strip() or 'General Inspection',
                current_service=data.get('current_service', '').strip() or None,
                status=data.get('status', JobCard.STATUS_NEW),
                additional_remarks=data.get('additional_remarks', '').strip() or None,
                appointment_details=data.get('appointment_details', '').strip() or None,
                creator=user,
            )

            # Services
            for s in data.get('services', []):
                svc_obj = None
                if s.get('service_id'):
                    svc_obj = Service.objects.filter(id=s.get('service_id')).first()
                JobCardServiceItem.objects.create(
                    job_card=jc,
                    service=svc_obj,
                    service_name=s.get('service_name', svc_obj.name if svc_obj else 'Service'),
                    quantity=Decimal(str(s.get('quantity', 1) or 1)),
                    unit=s.get('unit', 'Unit') or 'Unit',
                    rate=Decimal(str(s.get('rate', 0) or 0)),
                    discount=Decimal(str(s.get('discount', 0) or 0)),
                    vat_percentage=Decimal(str(s.get('vat_percentage', 0) or 0)),
                    total_amount=Decimal(str(s.get('total_amount', 0) or 0)),
                    warranty=s.get('warranty', '').strip() or None,
                    warranty_period=s.get('warranty_period', '').strip() or None,
                    remarks=s.get('remarks', '').strip() or None,
                    creator=user,
                )

            # Parts / Accessories
            for p in data.get('parts', []):
                stk_obj = None
                if p.get('stock_item_id'):
                    stk_obj = Stock.objects.filter(id=p.get('stock_item_id')).first()
                JobCardPartItem.objects.create(
                    job_card=jc,
                    stock_item=stk_obj,
                    part_number=p.get('part_number', stk_obj.part_number if stk_obj else '').strip() or None,
                    alternate_part_number=p.get('alternate_part_number', stk_obj.alternate_part_number if stk_obj else '').strip() or None,
                    product_code=p.get('product_code', stk_obj.barcode if stk_obj else '').strip() or None,
                    product_name=p.get('product_name', stk_obj.item_name if stk_obj else 'Part'),
                    current_stock=Decimal(str(p.get('current_stock', stk_obj.quantity if stk_obj else 0) or 0)),
                    unit=p.get('unit', stk_obj.unit if stk_obj else 'Pcs') or 'Pcs',
                    rate=Decimal(str(p.get('rate', 0) or 0)),
                    rate_with_tax=Decimal(str(p.get('rate_with_tax', 0) or 0)),
                    quantity=Decimal(str(p.get('quantity', 1) or 1)),
                    discount=Decimal(str(p.get('discount', 0) or 0)),
                    vat_percentage=Decimal(str(p.get('vat_percentage', 0) or 0)),
                    total_amount=Decimal(str(p.get('total_amount', 0) or 0)),
                    remarks=p.get('remarks', '').strip() or None,
                    creator=user,
                )

            # Labour
            for l in data.get('labour', []):
                JobCardLabourItem.objects.create(
                    job_card=jc,
                    labour_particulars=l.get('labour_particulars', 'Labour Charge'),
                    quantity=Decimal(str(l.get('quantity', 1) or 1)),
                    rate=Decimal(str(l.get('rate', 0) or 0)),
                    discount=Decimal(str(l.get('discount', 0) or 0)),
                    vat_percentage=Decimal(str(l.get('vat_percentage', 0) or 0)),
                    total_amount=Decimal(str(l.get('total_amount', 0) or 0)),
                    remarks=l.get('remarks', '').strip() or None,
                    creator=user,
                )

            # Extras
            for e in data.get('extras', []):
                JobCardExtraItem.objects.create(
                    job_card=jc,
                    extra_details=e.get('extra_details', 'Extra Item'),
                    quantity=Decimal(str(e.get('quantity', 1) or 1)),
                    rate=Decimal(str(e.get('rate', 0) or 0)),
                    discount=Decimal(str(e.get('discount', 0) or 0)),
                    discount_type=e.get('discount_type', 'amount') or 'amount',
                    discount_percentage=Decimal(str(e.get('discount_percentage', 0) or 0)),
                    vat_percentage=Decimal(str(e.get('vat_percentage', 0) or 0)),
                    total_amount=Decimal(str(e.get('total_amount', 0) or 0)),
                    remarks=e.get('remarks', '').strip() or None,
                    creator=user,
                )

            jc.calculate_estimated_cost()
            jc.save()

        return JsonResponse({
            'success': True,
            'message': 'Job Card created successfully',
            'job_card_id': str(jc.id),
            'job_number': jc.job_number,
            'estimated_cost': float(jc.estimated_cost),
        })

    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@csrf_exempt
def api_job_card_from_quotation(request, quotation_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        from client_management.models import Quotation

        with transaction.atomic():
            quotation = Quotation.objects.select_for_update().select_related(
                'customer', 'vehicle', 'branch'
            ).filter(id=quotation_id, is_deleted=False).first()
            if not quotation:
                return JsonResponse({'success': False, 'message': 'Quotation not found'}, status=404)

            company = getattr(getattr(user, 'profile', None), 'company', None)
            branch_admin = getattr(user, 'managed_branch', None)
            if not company and branch_admin:
                company = branch_admin.company
            if not company:
                company = getattr(getattr(user, 'staff_profile', None), 'company', None)
            quote_company = (quotation.branch.company if quotation.branch else None) or quotation.customer.company
            if not company or str(company.id) != str(quote_company.id):
                return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
            if branch_admin and quotation.branch_id and str(branch_admin.id) != str(quotation.branch_id):
                return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
            if not quotation.is_accepted:
                return JsonResponse({'success': False, 'message': 'Accept the quotation before conversion'}, status=409)

            # The one-to-one relation remains occupied even if a job card is soft-deleted.
            existing = JobCard.objects.filter(quotation=quotation).first()
            if existing:
                return JsonResponse({
                    'success': True,
                    'already_converted': True,
                    'job_card_id': str(existing.id),
                    'job_number': existing.job_number,
                    'estimated_cost': float(existing.estimated_cost or 0),
                })

            branch = quotation.branch or quotation.customer.branch
            if not branch:
                return JsonResponse({'success': False, 'message': 'Quotation has no branch'}, status=400)

            quotation_items = list(quotation.items.filter(is_deleted=False).select_related('service', 'stock_item'))
            jc = JobCard.objects.create(
                company=quote_company,
                branch=branch,
                customer=quotation.customer,
                vehicle=quotation.vehicle,
                quotation=quotation,
                current_section='General Inspection',
                current_service=quotation_items[0].service_name if quotation_items else '',
                additional_remarks=quotation.additional_services or None,
                creator=user,
            )

            for item in quotation_items:
                quantity = item.quantity or Decimal('1')
                line_total = item.rate * quantity
                if item.stock_item_id:
                    stock = item.stock_item
                    JobCardPartItem.objects.create(
                        job_card=jc,
                        stock_item=stock,
                        part_number=stock.part_number if stock else None,
                        alternate_part_number=stock.alternate_part_number if stock else None,
                        product_code=stock.barcode if stock else None,
                        product_name=item.stock_item_name or (stock.item_name if stock else 'Part'),
                        current_stock=stock.quantity if stock else 0,
                        unit=stock.unit if stock else 'Pcs',
                        rate=item.rate,
                        rate_with_tax=item.rate,
                        quantity=quantity,
                        total_amount=line_total,
                        creator=user,
                    )
                else:
                    free_topup = (item.free_topup or '').strip()
                    JobCardServiceItem.objects.create(
                        job_card=jc,
                        service=item.service,
                        service_name=item.service_name or (item.service.name if item.service else 'Service'),
                        quantity=quantity,
                        unit='Unit',
                        rate=item.rate,
                        total_amount=line_total,
                        warranty=str(item.warranty_years or ''),
                        warranty_period='years' if item.warranty_years else '',
                        remarks=f'Free top-up: {free_topup}' if free_topup else '',
                        creator=user,
                    )

            for extra in quotation.extras.filter(is_deleted=False):
                JobCardExtraItem.objects.create(
                    job_card=jc,
                    extra_details=extra.name,
                    quantity=extra.quantity or Decimal('1'),
                    rate=extra.price,
                    discount=extra.discount,
                    discount_type=extra.discount_type or 'amount',
                    discount_percentage=extra.discount_percentage,
                    total_amount=extra.total,
                    remarks=extra.remarks or '',
                    creator=user,
                )

            jc.estimated_cost = quotation.grand_total
            jc.save(update_fields=['estimated_cost', 'date_updated'])

        return JsonResponse({
            'success': True,
            'already_converted': False,
            'job_card_id': str(jc.id),
            'job_number': jc.job_number,
            'estimated_cost': float(jc.estimated_cost or 0),
        })
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@csrf_exempt
def api_job_card_update(request, job_card_id):
    """Updates an existing job card and replaces its items."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        jc = JobCard.objects.get(id=job_card_id, is_deleted=False)
        data = json.loads(request.body)

        delivery_date_str = data.get('expected_delivery_date')
        if delivery_date_str:
            for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %I:%M %p', '%Y-%m-%d', '%d-%m-%Y %H:%M', '%d-%m-%Y'):
                try:
                    expected_delivery = datetime.strptime(delivery_date_str, fmt)
                    if timezone.is_naive(expected_delivery):
                        expected_delivery = timezone.make_aware(expected_delivery)
                    jc.expected_delivery_date = expected_delivery
                    break
                except ValueError:
                    pass

        if 'delivery_lead_time' in data:
            jc.delivery_lead_time = data['delivery_lead_time']
        if 'current_section' in data:
            jc.current_section = data['current_section']
        if 'current_service' in data:
            jc.current_service = data['current_service']
        if 'status' in data:
            jc.status = data['status']
        if 'additional_remarks' in data:
            jc.additional_remarks = data['additional_remarks']
        if 'appointment_details' in data:
            jc.appointment_details = data['appointment_details']

        with transaction.atomic():
            # If services array provided, update items
            if 'services' in data:
                jc.service_items.all().delete()
                for s in data['services']:
                    svc_obj = None
                    if s.get('service_id'):
                        svc_obj = Service.objects.filter(id=s.get('service_id')).first()
                    JobCardServiceItem.objects.create(
                        job_card=jc,
                        service=svc_obj,
                        service_name=s.get('service_name', svc_obj.name if svc_obj else 'Service'),
                        quantity=Decimal(str(s.get('quantity', 1) or 1)),
                        unit=s.get('unit', 'Unit') or 'Unit',
                        rate=Decimal(str(s.get('rate', 0) or 0)),
                        discount=Decimal(str(s.get('discount', 0) or 0)),
                        vat_percentage=Decimal(str(s.get('vat_percentage', 0) or 0)),
                        total_amount=Decimal(str(s.get('total_amount', 0) or 0)),
                        warranty=s.get('warranty', '').strip() or None,
                        warranty_period=s.get('warranty_period', '').strip() or None,
                        remarks=s.get('remarks', '').strip() or None,
                        creator=user,
                    )

            if 'parts' in data:
                jc.part_items.all().delete()
                for p in data['parts']:
                    stk_obj = None
                    if p.get('stock_item_id'):
                        stk_obj = Stock.objects.filter(id=p.get('stock_item_id')).first()
                    JobCardPartItem.objects.create(
                        job_card=jc,
                        stock_item=stk_obj,
                        part_number=p.get('part_number', stk_obj.part_number if stk_obj else '').strip() or None,
                        alternate_part_number=p.get('alternate_part_number', stk_obj.alternate_part_number if stk_obj else '').strip() or None,
                        product_code=p.get('product_code', stk_obj.barcode if stk_obj else '').strip() or None,
                        product_name=p.get('product_name', stk_obj.item_name if stk_obj else 'Part'),
                        current_stock=Decimal(str(p.get('current_stock', stk_obj.quantity if stk_obj else 0) or 0)),
                        unit=p.get('unit', stk_obj.unit if stk_obj else 'Pcs') or 'Pcs',
                        rate=Decimal(str(p.get('rate', 0) or 0)),
                        rate_with_tax=Decimal(str(p.get('rate_with_tax', 0) or 0)),
                        quantity=Decimal(str(p.get('quantity', 1) or 1)),
                        discount=Decimal(str(p.get('discount', 0) or 0)),
                        vat_percentage=Decimal(str(p.get('vat_percentage', 0) or 0)),
                        total_amount=Decimal(str(p.get('total_amount', 0) or 0)),
                        remarks=p.get('remarks', '').strip() or None,
                        creator=user,
                    )

            if 'labour' in data:
                jc.labour_items.all().delete()
                for l in data['labour']:
                    JobCardLabourItem.objects.create(
                        job_card=jc,
                        labour_particulars=l.get('labour_particulars', 'Labour Charge'),
                        quantity=Decimal(str(l.get('quantity', 1) or 1)),
                        rate=Decimal(str(l.get('rate', 0) or 0)),
                        discount=Decimal(str(l.get('discount', 0) or 0)),
                        vat_percentage=Decimal(str(l.get('vat_percentage', 0) or 0)),
                        total_amount=Decimal(str(l.get('total_amount', 0) or 0)),
                        remarks=l.get('remarks', '').strip() or None,
                        creator=user,
                    )

            if 'extras' in data:
                jc.extra_items.all().delete()
                for e in data['extras']:
                    JobCardExtraItem.objects.create(
                        job_card=jc,
                        extra_details=e.get('extra_details', 'Extra Item'),
                        quantity=Decimal(str(e.get('quantity', 1) or 1)),
                        rate=Decimal(str(e.get('rate', 0) or 0)),
                        discount=Decimal(str(e.get('discount', 0) or 0)),
                        discount_type=e.get('discount_type', 'amount') or 'amount',
                        discount_percentage=Decimal(str(e.get('discount_percentage', 0) or 0)),
                        vat_percentage=Decimal(str(e.get('vat_percentage', 0) or 0)),
                        total_amount=Decimal(str(e.get('total_amount', 0) or 0)),
                        remarks=e.get('remarks', '').strip() or None,
                        creator=user,
                    )

            jc.calculate_estimated_cost()
            jc.updater = user
            jc.save()

        return JsonResponse({
            'success': True,
            'message': 'Job Card updated successfully',
            'job_card_id': str(jc.id),
            'job_number': jc.job_number,
            'estimated_cost': float(jc.estimated_cost),
        })

    except JobCard.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Job Card not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@csrf_exempt
def api_job_card_update_status(request, job_card_id):
    """Quick update for status, current section, and current service."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        jc = JobCard.objects.get(id=job_card_id, is_deleted=False)
        data = json.loads(request.body)

        new_status = data.get('status')
        if new_status:
            valid_statuses = [c[0] for c in JobCard.STATUS_CHOICES]
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': f'Invalid status. Valid: {valid_statuses}'}, status=400)
            jc.status = new_status

        if 'current_section' in data:
            jc.current_section = data['current_section']
        if 'current_service' in data:
            jc.current_service = data['current_service']

        jc.updater = user
        jc.save()

        return JsonResponse({
            'success': True,
            'message': 'Status updated successfully',
            'status': jc.status,
            'status_display': jc.get_status_display(),
            'current_section': jc.current_section,
            'current_service': jc.current_service,
        })
    except JobCard.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Job Card not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@csrf_exempt
def api_job_card_accessories_search(request):
    """Search for accessories, spare parts, and products in Stock by part_number, barcode, or name."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    company = getattr(getattr(user, 'profile', None), 'company', None)
    q = request.GET.get('q', '').strip()

    stocks_qs = Stock.objects.filter(is_deleted=False)
    if company:
        stocks_qs = stocks_qs.filter(company=company)

    if q:
        stocks_qs = stocks_qs.filter(
            Q(item_name__icontains=q) |
            Q(brand__icontains=q) |
            Q(barcode__icontains=q) |
            Q(part_number__icontains=q) |
            Q(alternate_part_number__icontains=q)
        )

    from master.models import PurchaseInvoiceItem
    results = []
    for s in stocks_qs.select_related('group', 'sub_group')[:50]:
        last_purchase = PurchaseInvoiceItem.objects.filter(stock_item=s, is_deleted=False).order_by('-date_added').first()
        purchase_price = float(last_purchase.rate) if last_purchase else 0.0
        profit_margin = float(s.profit_margin_percent or 0.0)

        if float(getattr(s, 'selling_price', 0) or 0) > 0:
            rate = float(s.selling_price)
        elif purchase_price > 0:
            rate = round(purchase_price * (1 + profit_margin / 100.0), 2)
        else:
            rate = 0.0

        tax_percent = float((s.cgst_percent or 0) + (s.sgst_percent or 0) + (s.igst_percent or 0))
        rate_with_tax = round(rate * (1 + tax_percent / 100.0), 2)

        results.append({
            'id': str(s.id),
            'part_number': s.part_number or '',
            'alternate_part_number': s.alternate_part_number or '',
            'product_code': s.barcode or '',
            'product_name': s.item_name,
            'brand': s.brand or '',
            'current_stock': float(s.quantity or 0),
            'unit': s.unit or 'Pcs',
            'rate': rate,
            'tax_percent': tax_percent,
            'rate_with_tax': rate_with_tax,
        })

    return JsonResponse({'success': True, 'results': results})


@csrf_exempt
def api_job_card_metadata(request):
    """Returns dropdown metadata for customer types, vehicles, makes, models, sections, etc."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    customer_types = list(CustomerType.objects.filter(is_deleted=False).values('id', 'name'))
    for ct in customer_types:
        ct['id'] = str(ct['id'])

    makes = list(VehicleMake.objects.filter(is_deleted=False).order_by('name').values('id', 'name'))
    for m in makes:
        m['id'] = str(m['id'])

    colors = list(VehicleColor.objects.filter(is_deleted=False).order_by('name').values('id', 'name'))
    for c in colors:
        c['id'] = str(c['id'])

    emission_standards = list(EmissionStandard.objects.filter(is_deleted=False, is_active=True).values('id', 'name', 'fuel_type'))
    for es in emission_standards:
        es['id'] = str(es['id'])

    vehicle_types = list(VehicleType.objects.filter(is_deleted=False).order_by('name').values('id', 'name'))
    for vt in vehicle_types:
        vt['id'] = str(vt['id'])

    models = list(VehicleTypeModel.objects.filter(is_deleted=False).select_related('vehicle_type').order_by('name').values('id', 'name', 'vehicle_type__name', 'vehicle_type_id'))
    for md in models:
        md['id'] = str(md['id'])
        md['vehicle_type_id'] = str(md['vehicle_type_id']) if md['vehicle_type_id'] else ''

    # Pre-configured sections for job order progress
    sections = [
        'General Inspection',
        'Washing & Cleaning',
        'Detailing & Polishing',
        'Mechanical & Service',
        'Electrical & AC',
        'Bodyshop & Denting',
        'Painting',
        'Quality Inspection',
        'Ready for Delivery',
    ]

    fuel_types = ['Petrol', 'Diesel', 'CNG', 'LPG', 'Electric', 'Hybrid']
    transmission_types = ['Automatic', 'Manual', 'CVT', 'DCT', 'AMT']
    segments = ['Hatchback', 'Sedan', 'Compact SUV', 'SUV', 'MUV / MPV', 'Luxury', 'Pickup', 'Van', 'Motorcycle']

    return JsonResponse({
        'success': True,
        'customer_types': customer_types,
        'vehicle_makes': makes,
        'vehicle_colors': colors,
        'emission_standards': emission_standards,
        'vehicle_types': vehicle_types,
        'vehicle_models': models,
        'sections': sections,
        'fuel_types': fuel_types,
        'transmission_types': transmission_types,
        'segments': segments,
    })


@csrf_exempt
def api_job_card_add_vehicle(request):
    """Registers a new vehicle for an existing customer."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        plate_number = (data.get('plate_number') or data.get('vehicle_number', '')).strip().upper()

        if not customer_id or not plate_number:
            return JsonResponse({'success': False, 'message': 'Customer and Plate Number are required'}, status=400)

        customer = Customer.objects.get(id=customer_id, is_deleted=False)

        # Check if already exists for this customer
        existing = CustomerVehicle.objects.filter(customer=customer, vehicle_number=plate_number, is_deleted=False).first()
        if existing:
            return JsonResponse({'success': False, 'message': f'Vehicle {plate_number} already registered for this customer'}, status=400)

        make = None
        if data.get('make_id'):
            make = VehicleMake.objects.filter(id=data.get('make_id'), is_deleted=False).first()

        brand_model = None
        if data.get('brand_model_id'):
            brand_model = VehicleBrandModel.objects.filter(id=data.get('brand_model_id'), is_deleted=False).first()

        vm = None
        if data.get('vehicle_type_model_id'):
            vm = VehicleTypeModel.objects.filter(id=data.get('vehicle_type_model_id'), is_deleted=False).first()
        elif brand_model and hasattr(brand_model, 'vehicle_type_model'):
            vm = brand_model.vehicle_type_model
        if not vm:
            vm = VehicleTypeModel.objects.filter(is_deleted=False).first()

        color = None
        if data.get('color_id'):
            color = VehicleColor.objects.filter(id=data.get('color_id'), is_deleted=False).first()

        emission = None
        if data.get('emission_standard_id'):
            emission = EmissionStandard.objects.filter(id=data.get('emission_standard_id'), is_deleted=False).first()

        vehicle = CustomerVehicle.objects.create(
            customer=customer,
            vehicle_number=plate_number,
            vehicle_type_model=vm,
            vehicle_type=vm.vehicle_type if vm else None,
            make=make,
            brand_model=brand_model,
            color=color,
            emission_standard=emission,
            fuel_type=data.get('fuel_type'),
            chassis_number=data.get('chassis_number', '').strip() or None,
            engine_number=data.get('engine_number', '').strip() or None,
            model_year=data.get('model_year', '').strip() or None,
            variant_trim=data.get('variant_trim', '').strip() or None,
            segment=data.get('segment', '').strip() or None,
            transmission_type=data.get('transmission_type', '').strip() or None,
            creator=user,
            auto_id=get_auto_id(CustomerVehicle),
        )

        eff_es = vehicle.emission_standard or (vehicle.vehicle_type_model.emission_standard if (vehicle.vehicle_type_model) else None)

        return JsonResponse({
            'success': True,
            'message': 'Vehicle registered successfully',
            'vehicle': {
                'id': str(vehicle.id),
                'no': vehicle.vehicle_number,
                'vehicle_number': vehicle.vehicle_number,
                'type': vehicle.vehicle_type_model.name if vehicle.vehicle_type_model else '',
                'vehicle_type': vehicle.vehicle_type_model.vehicle_type.name if (vehicle.vehicle_type_model and vehicle.vehicle_type_model.vehicle_type) else '',
                'make': vehicle.make.name if vehicle.make else '',
                'model': (vehicle.brand_model.name if vehicle.brand_model else '') or (vehicle.vehicle_type_model.name if vehicle.vehicle_type_model else ''),
                'segment': vehicle.segment or '',
                'fuel_type': vehicle.fuel_type or '',
                'chassis_number': vehicle.chassis_number or '',
                'engine_number': vehicle.engine_number or '',
                'emission_standard': eff_es.name if eff_es else '',
            }
        })

    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Customer not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


def generate_job_card_pdf_file(job_card, base_url=None):
    import sys
    import os
    from django.template.loader import render_to_string
    from django.conf import settings

    if sys.platform == 'darwin':
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = '/opt/homebrew/lib:' + os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
    from weasyprint import HTML

    currency = '₹'
    if job_card.branch and job_card.branch.company and job_card.branch.company.country:
        currency = getattr(job_card.branch.company.country, 'currency_symbol', '₹') or '₹'

    services = list(job_card.service_items.filter(is_deleted=False))
    parts = list(job_card.part_items.filter(is_deleted=False))
    labour = list(job_card.labour_items.filter(is_deleted=False))
    extras = list(job_card.extra_items.filter(is_deleted=False))

    services_subtotal = sum(float(s.total_amount or 0) for s in services)
    parts_subtotal = sum(float(p.total_amount or 0) for p in parts)
    labour_subtotal = sum(float(l.total_amount or 0) for l in labour)
    extras_subtotal = sum(float(e.total_amount or 0) for e in extras)
    grand_total = float(job_card.estimated_cost or (services_subtotal + parts_subtotal + labour_subtotal + extras_subtotal))

    company = job_card.company or (job_card.branch.company if job_card.branch else None)
    company_logo = None
    if company:
        logo_field = getattr(company, 'logo_color', None) or getattr(company, 'logo_bw', None) or getattr(company, 'logo', None)
        if logo_field:
            try:
                if hasattr(logo_field, 'path') and os.path.exists(logo_field.path):
                    company_logo = 'file://' + os.path.abspath(logo_field.path)
                elif hasattr(logo_field, 'url'):
                    company_logo = logo_field.url
            except Exception:
                company_logo = getattr(logo_field, 'url', None)
    if not company_logo and job_card.branch and getattr(job_card.branch, 'logo', None):
        try:
            if hasattr(job_card.branch.logo, 'path') and os.path.exists(job_card.branch.logo.path):
                company_logo = 'file://' + os.path.abspath(job_card.branch.logo.path)
            elif hasattr(job_card.branch.logo, 'url'):
                company_logo = job_card.branch.logo.url
        except Exception:
            company_logo = getattr(job_card.branch.logo, 'url', None)

    context = {
        'job_card': job_card,
        'company': company,
        'company_logo': company_logo,
        'currency': currency,
        'services': services,
        'parts': parts,
        'labour': labour,
        'extras': extras,
        'services_subtotal': services_subtotal,
        'parts_subtotal': parts_subtotal,
        'labour_subtotal': labour_subtotal,
        'extras_subtotal': extras_subtotal,
        'grand_total': grand_total,
    }

    html_string = render_to_string('job_card/job_card_pdf.html', context)

    media_dir = os.path.join(settings.BASE_DIR, 'media', 'job_cards')
    os.makedirs(media_dir, exist_ok=True)

    clean_no = str(job_card.job_number).replace('/', '_')
    pdf_filename = f"job_card-{clean_no}.pdf"
    pdf_path = os.path.join(media_dir, pdf_filename)

    html = HTML(string=html_string, base_url=base_url)
    html.write_pdf(target=pdf_path)

    if not base_url or '127.0.0.1' in base_url or 'localhost' in base_url:
        base_url = 'http://68.183.94.11:78'

    if not base_url.endswith('/'):
        base_url += '/'
    return f"{base_url}media/job_cards/{pdf_filename}"


def api_job_card_pdf(request, job_card_id):
    """Generates and returns the Job Card PDF URL."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)

    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        jc = JobCard.objects.select_related(
            'customer', 'vehicle', 'branch', 'company', 'vehicle__make', 'vehicle__brand_model',
            'vehicle__vehicle_type_model', 'vehicle__vehicle_type_model__vehicle_type', 'vehicle__color'
        ).get(id=job_card_id, is_deleted=False)
    except JobCard.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Job Card not found'}, status=404)

    base_url = request.build_absolute_uri('/')
    try:
        pdf_url = generate_job_card_pdf_file(jc, base_url)
        return JsonResponse({'success': True, 'pdf_url': pdf_url, 'job_number': jc.job_number})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Failed to generate PDF: {str(e)}'}, status=500)


def _job_pipeline_scope(user):
    profile = getattr(user, 'profile', None)
    branch = getattr(user, 'managed_branch', None)
    if not branch:
        branch = getattr(getattr(user, 'staff_profile', None), 'branch', None)
    company = getattr(profile, 'company', None) or getattr(branch, 'company', None)
    if not company:
        company = getattr(getattr(user, 'staff_profile', None), 'company', None)
    return company, branch


def _job_lead_data(lead):
    return {
        'id': str(lead.id), 'customer_name': lead.customer_name, 'phone_number': lead.phone_number,
        'branch_id': str(lead.branch_id or ''),
        'lead_number': f'JL-{lead.auto_id}', 'lead_date': lead.lead_date.isoformat() if lead.lead_date else (lead.date_added.date().isoformat() if lead.date_added else ''),
        'whatsapp_number': lead.whatsapp_number or '', 'lead_generation_mode': lead.lead_generation_mode or '',
        'reference': lead.reference or '', 'state': lead.state or '', 'city': lead.city or '', 'email': lead.email or '', 'expected_value': float(lead.expected_value or 0),
        'status': lead.status, 'success_chance': float(lead.success_chance) if lead.success_chance is not None else None,
        'lost_reason': lead.lost_reason or '', 'next_follow_up_date': lead.next_follow_up_date.isoformat() if lead.next_follow_up_date else '',
        'service_name': lead.service_name or '', 'staff_name': lead.staff.name if lead.staff_id else (lead.staff_name or ''), 'staff_id': str(lead.staff_id or ''),
        'customer_type_id': str(lead.customer_type_id or ''), 'customer_type_name': lead.customer_type.name if lead.customer_type_id else '',
        'vehicle_number': lead.vehicle_number or '', 'vehicle_make': lead.vehicle_make or '',
        'vehicle_type_id': str(lead.vehicle_type_id or ''), 'vehicle_segment_id': str(lead.vehicle_segment_id or ''),
        'vehicle_make_id': str(lead.vehicle_make_master_id or ''), 'vehicle_model_id': str(lead.vehicle_model_master_id or ''),
        'vehicle_color_id': str(lead.vehicle_color_id or ''), 'vehicle_emission_standard_id': str(lead.vehicle_emission_standard_id or ''),
        'vehicle_fuel_type': lead.vehicle_fuel_type or '', 'vehicle_wheel_type': lead.vehicle_wheel_type or '',
        'vehicle_model': lead.vehicle_model or '', 'customer_id': str(lead.customer_id) if lead.customer_id else '',
        'vehicle_details': ' '.join(filter(None, [lead.vehicle_number, lead.vehicle_make, lead.vehicle_model])),
        'vehicle_id': str(lead.vehicle_id) if lead.vehicle_id else '',
        'quotation_count': lead.quotations.filter(is_deleted=False).count(),
        'service_interests': [{'id': str(item.id), 'service_id': str(item.service_id or ''), 'category_name': item.category_name or '', 'service_name': item.service_name, 'expected_value': float(item.expected_value or 0)} for item in lead.service_interests.filter(is_deleted=False)],
        'follow_ups': [{'id': str(f.id), 'remarks': f.remarks, 'next_follow_up_date': f.next_follow_up_date.isoformat() if f.next_follow_up_date else '', 'status': f.status, 'success_chance': float(f.success_chance) if f.success_chance is not None else None, 'lost_reason': f.lost_reason or '', 'date_added': f.date_added.isoformat() if f.date_added else ''} for f in lead.follow_ups.filter(is_deleted=False)],
    }


@csrf_exempt
def api_job_leads(request):
    from .models import JobLead, JobLeadGenerationMode, JobLeadServiceInterest
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    if not company:
        return JsonResponse({'status': 'error', 'message': 'Company not found'}, status=400)
    if request.method == 'GET':
        qs = JobLead.objects.filter(company=company, is_deleted=False)
        if branch:
            qs = qs.filter(branch=branch)
        status = request.GET.get('status', '')
        if status in dict(JobLead.STATUS_CHOICES):
            qs = qs.filter(status=status)
        search = request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(Q(customer_name__icontains=search) | Q(phone_number__icontains=search) | Q(vehicle_number__icontains=search) | Q(vehicle_make__icontains=search) | Q(vehicle_model__icontains=search))
        return JsonResponse({'status': 'success', 'leads': [_job_lead_data(lead) for lead in qs]})
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        from core.functions import get_auto_id
        data = json.loads(request.body or '{}')
        name = (data.get('customer_name') or '').strip()
        phone = (data.get('phone_number') or '').strip()
        from datetime import date
        from decimal import Decimal, InvalidOperation
        from django.db import transaction
        from client_management.models import Staff, CustomerType
        from service_management.models import Service
        interests = data.get('service_interests') or []
        if not name or not phone or not interests or not data.get('staff_id') or not data.get('customer_type_id') or not data.get('lead_date') or not data.get('next_follow_up_date') or not (data.get('lead_generation_mode') or '').strip():
            return JsonResponse({'status': 'error', 'message': 'Lead date, staff, lead mode, customer type, mobile, customer name, at least one service and next follow-up date are required'}, status=400)
        try:
            lead_date = date.fromisoformat(data['lead_date'])
            next_date = date.fromisoformat(data['next_follow_up_date'])
            staff = Staff.objects.get(id=data['staff_id'], company=company, is_deleted=False, branch=branch) if branch else Staff.objects.get(id=data['staff_id'], company=company, is_deleted=False)
            customer_type = CustomerType.objects.get(id=data['customer_type_id'], is_deleted=False)
            expected = Decimal('0')
            parsed_items = []
            for item in interests:
                service = Service.objects.get(id=item.get('service_id'), is_active=True, is_deleted=False)
                if branch and not service.service_branches.filter(branch=branch, is_enabled=True, is_deleted=False).exists():
                    raise ValueError('Selected service is not enabled for your branch')
                amount = Decimal(str(item.get('expected_value', 0)))
                if amount < 0:
                    raise ValueError('Expected value cannot be negative')
                expected += amount
                parsed_items.append((service, amount))
        except (ValueError, InvalidOperation, Staff.DoesNotExist, CustomerType.DoesNotExist, Service.DoesNotExist) as exc:
            return JsonResponse({'status': 'error', 'message': f'Invalid lead details: {exc}'}, status=400)
        with transaction.atomic():
            mode = (data.get('lead_generation_mode') or '').strip()
            JobLeadGenerationMode.objects.get_or_create(company=company, name__iexact=mode, defaults={'name': mode, 'auto_id': get_auto_id(JobLeadGenerationMode), 'creator': user})
            lead = JobLead.objects.create(
            company=company, branch=branch, customer_name=name, phone_number=phone,
            lead_date=lead_date, staff=staff, staff_name=staff.name, customer_type=customer_type,
            whatsapp_number=data.get('whatsapp_number') or '', lead_generation_mode=mode,
            reference=data.get('reference') or '', state=data.get('state') or '', city=data.get('city') or '', email=data.get('email') or '', expected_value=expected,
            next_follow_up_date=next_date,
            service_name=', '.join(service.name for service, _ in parsed_items),
            vehicle_number=data.get('vehicle_number') or '', vehicle_make=data.get('vehicle_make') or '',
            vehicle_model=data.get('vehicle_model') or '', vehicle_type_id=data.get('vehicle_type_id') or None,
            vehicle_segment_id=data.get('vehicle_segment_id') or None, vehicle_make_master_id=data.get('vehicle_make_id') or None,
            vehicle_model_master_id=data.get('vehicle_model_id') or None, vehicle_color_id=data.get('vehicle_color_id') or None,
            vehicle_emission_standard_id=data.get('vehicle_emission_standard_id') or None,
            vehicle_fuel_type=data.get('vehicle_fuel_type') or '', vehicle_wheel_type=data.get('vehicle_wheel_type') or '',
            auto_id=get_auto_id(JobLead), creator=user,
            )
            for service, amount in parsed_items:
                JobLeadServiceInterest.objects.create(lead=lead, service=service, category_name=service.service_type.name, service_name=service.name, expected_value=amount, auto_id=get_auto_id(JobLeadServiceInterest), creator=user)
        return JsonResponse({'status': 'success', 'lead': _job_lead_data(lead)})
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)


@csrf_exempt
def api_job_lead_update(request, lead_id):
    from .models import JobLead
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    try:
        company, branch = _job_pipeline_scope(user)
        lead = JobLead.objects.get(id=lead_id, company=company, is_deleted=False)
        if branch and lead.branch_id != branch.id:
            return JsonResponse({'status': 'error', 'message': 'Forbidden'}, status=403)
        data = json.loads(request.body or '{}')
        for field in ('customer_name', 'phone_number', 'whatsapp_number', 'lead_generation_mode', 'reference', 'state', 'city', 'email', 'service_name', 'staff_name', 'vehicle_number', 'vehicle_make', 'vehicle_model', 'lost_reason'):
            if field in data:
                setattr(lead, field, data[field] or '')
        if 'expected_value' in data:
            lead.expected_value = data['expected_value'] or 0
        lead.save()
        return JsonResponse({'status': 'success', 'lead': _job_lead_data(lead)})
    except JobLead.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Lead not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)


@csrf_exempt
def api_job_lead_delete(request, lead_id):
    from .models import JobLead
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    lead = JobLead.objects.filter(id=lead_id, company=company, is_deleted=False).first()
    if not lead or (branch and lead.branch_id != branch.id):
        return JsonResponse({'success': False, 'message': 'Lead not found'}, status=404)
    lead.is_deleted = True
    lead.save(update_fields=['is_deleted', 'date_updated'])
    return JsonResponse({'success': True})


@csrf_exempt
def api_job_lead_follow_up(request, lead_id):
    from datetime import date
    from decimal import Decimal
    from core.functions import get_auto_id
    from .models import JobLead, JobLeadFollowUp
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    try:
        company, branch = _job_pipeline_scope(user)
        lead = JobLead.objects.get(id=lead_id, company=company, is_deleted=False)
        if branch and lead.branch_id != branch.id:
            return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
        data = json.loads(request.body or '{}')
        remarks = (data.get('remarks') or '').strip()
        status = data.get('status', JobLead.STATUS_FOLLOW_UP)
        lost_reason = (data.get('lost_reason') or '').strip()
        if not remarks or status not in dict(JobLead.STATUS_CHOICES):
            return JsonResponse({'success': False, 'message': 'Remarks and a valid status are required'}, status=400)
        if status == JobLead.STATUS_LOST and not lost_reason:
            return JsonResponse({'success': False, 'message': 'A reason is required for lost leads'}, status=400)
        followup_date = data.get('next_follow_up_date') or None
        if followup_date:
            date.fromisoformat(followup_date)
        chance = data.get('success_chance')
        followup = JobLeadFollowUp.objects.create(
            lead=lead, remarks=remarks, next_follow_up_date=followup_date, status=status,
            success_chance=Decimal(str(chance)) if chance not in (None, '') else None,
            lost_reason=lost_reason, auto_id=get_auto_id(JobLeadFollowUp), creator=user,
        )
        lead.status, lead.next_follow_up_date, lead.success_chance, lead.lost_reason = status, followup_date, followup.success_chance, lost_reason
        lead.save(update_fields=['status', 'next_follow_up_date', 'success_chance', 'lost_reason', 'date_updated'])
        return JsonResponse({'success': True, 'follow_up_id': str(followup.id)})
    except JobLead.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Lead not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


@csrf_exempt
def api_job_lead_form_data(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    if not company:
        return JsonResponse({'success': False, 'message': 'Company not found'}, status=400)
    from client_management.models import Branch, CustomerType, Staff
    from master.models import State, VehicleType, VehicleTypeModel, VehicleMake, VehicleBrandModel, VehicleColor, EmissionStandard
    from service_management.models import Service, BranchService, CompanyService, BranchServiceCategory
    from .models import JobLeadGenerationMode
    if not branch:
        branch_id = request.GET.get('branch_id')
        branch = Branch.objects.filter(id=branch_id, company=company, is_deleted=False).first() if branch_id else Branch.objects.filter(company=company, is_deleted=False).order_by('name').first()
    staff = Staff.objects.filter(company=company, is_deleted=False)
    if branch:
        staff = staff.filter(branch=branch)
    enabled_ids = CompanyService.objects.filter(company=company, is_enabled=True).values_list('service_id', flat=True)
    enabled_ids = BranchService.objects.filter(branch=branch, is_enabled=True, is_deleted=False, service_id__in=enabled_ids).values_list('service_id', flat=True) if branch else []
    services = Service.objects.filter(id__in=enabled_ids, is_active=True, is_deleted=False)
    disabled_categories = BranchServiceCategory.objects.filter(branch=branch, is_enabled=False, is_deleted=False).values_list('service_type_id', flat=True) if branch else []
    services = services.exclude(service_type_id__in=disabled_categories).distinct()
    states = State.objects.filter(is_deleted=False)
    country = getattr(company, 'country', None)
    if country:
        states = states.filter(country=country)
    return JsonResponse({'success': True,
        'states': [{'id': str(s.id), 'name': s.name} for s in states.order_by('name')],
        'staff': [{'id': str(s.id), 'name': s.name} for s in staff.order_by('name')],
        'customer_types': [{'id': str(c.id), 'name': c.name} for c in CustomerType.objects.filter(is_deleted=False).exclude(name__icontains='Workshop').order_by('name')],
        'lead_modes': list(JobLeadGenerationMode.objects.filter(company=company, is_deleted=False).values_list('name', flat=True)),
        'service_categories': [{'id': str(c['service_type_id']), 'name': c['service_type__name'], 'slug': c['service_type__slug'] or ''} for c in services.values('service_type_id', 'service_type__name', 'service_type__slug').distinct().order_by('service_type__name')],
        'services': [{'id': str(s.id), 'name': s.name, 'category_id': str(s.service_type_id), 'category_name': s.service_type.name} for s in services.select_related('service_type').order_by('service_type__name', 'name')],
        'vehicle_types': [{'id': str(v.id), 'name': v.name} for v in VehicleType.objects.filter(is_active=True, is_deleted=False).order_by('name')],
        'vehicle_segments': [{'id': str(v.id), 'name': v.name, 'vehicle_type_id': str(v.vehicle_type_id)} for v in VehicleTypeModel.objects.filter(is_active=True, is_deleted=False).filter(Q(company=company)|Q(company__isnull=True)).exclude(disabled_companies=company).order_by('name')],
        'makes': [{'id': str(v.id), 'name': v.name} for v in VehicleMake.objects.filter(is_active=True, is_deleted=False).order_by('name')],
        'vehicle_models': [{'id': str(v.id), 'name': v.name, 'make_id': str(v.make_id), 'segment_id': str(v.vehicle_type_model_id), 'vehicle_type_model_id': str(v.vehicle_type_model_id)} for v in VehicleBrandModel.objects.filter(is_active=True, is_deleted=False).order_by('name')],
        'colors': [{'id': str(v.id), 'name': v.name} for v in VehicleColor.objects.filter(is_deleted=False).order_by('name')],
        'emission_standards': [{'id': str(v.id), 'name': v.name} for v in EmissionStandard.objects.filter(is_deleted=False).order_by('name')],
        'fuel_types': [{'id': value, 'name': label} for value, label in CustomerVehicle.FUEL_TYPE_CHOICES],
        'wheel_types': [{'id': value, 'name': label} for value, label in CustomerVehicle.WHEEL_TYPE_CHOICES],
    })


@csrf_exempt
def api_job_lead_history(request, lead_id):
    from .models import JobLead, JobQuotation
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    lead = JobLead.objects.filter(id=lead_id, company=company, is_deleted=False).first()
    if not lead or (branch and lead.branch_id != branch.id):
        return JsonResponse({'success': False, 'message': 'Lead not found'}, status=404)
    events = [{'type': 'lead_created', 'title': 'Lead created', 'date': lead.date_added.isoformat(), 'description': f"{lead.customer_name} · {lead.lead_generation_mode or ''}"}]
    for f in lead.follow_ups.filter(is_deleted=False):
        events.append({'type': 'follow_up', 'title': 'Follow-up', 'date': f.date_added.isoformat(), 'description': f.remarks, 'status': f.status, 'next_follow_up_date': f.next_follow_up_date.isoformat() if f.next_follow_up_date else ''})
    for q in lead.quotations.filter(is_deleted=False):
        title = 'Quotation revised' if q.revised_from_id else 'Quotation created'
        events.append({'type': 'quotation_created', 'title': title, 'date': q.date_added.isoformat(), 'description': f'{q.quotation_number} · {q.grand_total}'})
        if q.is_accepted and q.accepted_at:
            events.append({'type': 'quotation_accepted', 'title': 'Quotation accepted', 'date': q.accepted_at.isoformat(), 'description': q.quotation_number})
    events.sort(key=lambda event: event['date'])
    return JsonResponse({'success': True, 'events': events})


@csrf_exempt
def api_job_card_issue_options(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET allowed'}, status=405)
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, _branch = _job_pipeline_scope(user)
    if not company:
        return JsonResponse({'success': False, 'message': 'Company not found'}, status=400)
    from service_management.models import JobCardCategory, JobCardService, JobCardIssue
    categories = JobCardCategory.objects.filter(is_deleted=False).order_by('name')
    services = JobCardService.objects.filter(is_deleted=False, category__in=categories).select_related('category').order_by('category__name', 'name')
    issues = JobCardIssue.objects.filter(is_deleted=False, service__in=services).select_related('category', 'service').order_by('name')
    return JsonResponse({
        'success': True,
        'categories': [{'id': str(item.id), 'name': item.name} for item in categories],
        'services': [{'id': str(item.id), 'name': item.name, 'category_id': str(item.category_id)} for item in services],
        'issues': [{'id': str(item.id), 'name': item.name, 'category_id': str(item.category_id), 'service_id': str(item.service_id)} for item in issues],
    })


@csrf_exempt
def api_job_card_issue_create(request):
    from core.functions import get_auto_id
    from service_management.models import JobCardCategory, JobCardService, JobCardIssue
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
    company, _branch = _job_pipeline_scope(user)
    if not company:
        return JsonResponse({'success': False, 'message': 'Company not found'}, status=400)
    try:
        data = json.loads(request.body or '{}')
        category = JobCardCategory.objects.get(id=data.get('category_id'), is_deleted=False)
        service = JobCardService.objects.get(id=data.get('service_id'), category=category, is_deleted=False)
        name = (data.get('name') or '').strip()
        if not name or len(name) > 200:
            return JsonResponse({'success': False, 'message': 'Issue name is required and must be at most 200 characters'}, status=400)
        issue = JobCardIssue.objects.filter(category=category, service=service, name__iexact=name, is_deleted=False).first()
        created = issue is None
        if created:
            issue = JobCardIssue.objects.create(category=category, service=service, name=name, auto_id=get_auto_id(JobCardIssue), creator=user)
        return JsonResponse({'success': True, 'created': created, 'issue': {'id': str(issue.id), 'name': issue.name, 'category_id': str(issue.category_id), 'service_id': str(issue.service_id)}})
    except (JobCardCategory.DoesNotExist, JobCardService.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'Selected category or service is invalid'}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


@csrf_exempt
@transaction.atomic
def api_job_quotation_create(request):
    from decimal import Decimal
    from django.db import transaction
    from core.functions import get_auto_id
    from client_management.models import Customer, CustomerVehicle, CustomerType, Branch, Stock
    from master.models import VehicleTypeModel, VehicleMake, VehicleBrandModel, VehicleColor, EmissionStandard
    from service_management.models import Service
    from .models import JobLead, JobLeadFollowUp, JobQuotation, JobQuotationItem, JobQuotationExtra, JobQuotationIssue, JobQuotationIssuePhoto
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    stored_image_names = []
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'message': 'Only POST allowed'}, status=405)
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = json.loads(request.POST.get('payload') or '{}')
        else:
            data = json.loads(request.body or '{}')
        from service_management.models import JobCardCategory, JobCardService, JobCardIssue
        prepared_issues = []
        for index, row in enumerate(data.get('reported_issues') or []):
            category = JobCardCategory.objects.filter(id=row.get('category_id'), is_deleted=False).first()
            service = JobCardService.objects.filter(id=row.get('service_id'), category=category, is_deleted=False).first() if category else None
            issue = JobCardIssue.objects.filter(id=row.get('issue_id'), category=category, service=service, is_deleted=False).first() if row.get('issue_id') and category and service else None
            issue_text = (row.get('issue_text') or (issue.name if issue else '')).strip()
            photos = request.FILES.getlist(f'issue_{index}_photos') if request.FILES else []
            if not category or not service or not issue or not issue_text:
                return JsonResponse({'success': False, 'message': f'Issue row {index + 1} has invalid category, service, or issue'}, status=400)
            if len(photos) > 3:
                return JsonResponse({'success': False, 'message': f'Issue row {index + 1} can have at most 3 photos'}, status=400)
            for photo in photos:
                if photo.size > 10 * 1024 * 1024:
                    return JsonResponse({'success': False, 'message': 'Each issue photo must be 10 MB or smaller'}, status=400)
                try:
                    from PIL import Image
                    photo.seek(0)
                    image = Image.open(photo)
                    image.verify()
                    if image.format not in ('JPEG', 'PNG', 'WEBP'):
                        raise ValueError('Only JPEG, PNG, and WebP photos are supported')
                    photo.seek(0)
                except Exception:
                    return JsonResponse({'success': False, 'message': 'An uploaded issue photo is not a valid JPEG, PNG, or WebP image'}, status=400)
            prepared_issues.append((category, service, issue, issue_text, photos))
        company, branch = _job_pipeline_scope(user)
        lead = None
        if data.get('lead_id'):
            lead = JobLead.objects.get(id=data['lead_id'], company=company, is_deleted=False)
            if branch and lead.branch_id != branch.id:
                return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
        if not branch:
            requested_branch_id = data.get('branch_id') or (lead.branch_id if lead else None)
            branch = Branch.objects.filter(id=requested_branch_id, company=company, is_deleted=False).first() if requested_branch_id else Branch.objects.filter(company=company, is_deleted=False).order_by('name').first()
        if not branch:
            return JsonResponse({'success': False, 'message': 'A branch is required to create a Job Card quotation'}, status=400)

        customer_profile = data.get('customer_profile')
        vehicle_details = data.get('vehicle_details')
        if customer_profile is not None and vehicle_details is not None:
            profile = customer_profile
            vehicle_data = vehicle_details
            name = (profile.get('name') or '').strip()
            phone = (profile.get('phone') or '').strip()
            customer_type = CustomerType.objects.filter(id=profile.get('customer_type_id'), is_deleted=False).first()
            state = (profile.get('state') or '').strip()
            city = (profile.get('city') or '').strip()
            tax_number = (profile.get('tax_number') or '').strip()
            tin_number = (profile.get('tin_number') or '').strip()
            pan_number = (profile.get('pan_number') or '').strip()
            if not name or not phone or not customer_type or not state or not city:
                return JsonResponse({'success': False, 'message': 'Name, customer type, mobile, Emirate/State and city are required'}, status=400)
            if 'corporate' in customer_type.name.lower() and not (tax_number and tin_number and pan_number):
                return JsonResponse({'success': False, 'message': 'Tax Registration No, TIN and PAN are required for corporate customers'}, status=400)
            plate = (vehicle_data.get('vehicle_number') or '').strip().upper()
            segment = VehicleTypeModel.objects.filter(id=vehicle_data.get('segment_id'), is_active=True, is_deleted=False).first()
            make = VehicleMake.objects.filter(id=vehicle_data.get('make_id'), is_active=True, is_deleted=False).first()
            brand_model = VehicleBrandModel.objects.filter(id=vehicle_data.get('brand_model_id'), is_active=True, is_deleted=False).first()
            if not plate or not segment or not make or not brand_model:
                return JsonResponse({'success': False, 'message': 'Vehicle number, make, model and segment are required'}, status=400)
            if brand_model.make_id != make.id or brand_model.vehicle_type_model_id != segment.id:
                return JsonResponse({'success': False, 'message': 'Selected vehicle make, model and segment do not match'}, status=400)

            def normalized(value):
                return ''.join(ch for ch in (value or '').upper() if ch.isalnum())

            with transaction.atomic():
                customer = None
                phone_key = normalized(phone)
                for candidate in Customer.objects.filter(company=company, branch=branch, is_deleted=False).only('id', 'phone'):
                    if normalized(candidate.phone) == phone_key:
                        customer = Customer.objects.select_for_update().get(id=candidate.id)
                        break
                if customer is None:
                    customer = Customer.objects.create(
                        company=company, branch=branch, name=name, phone=phone, customer_type=customer_type,
                        customer_category='motor', creator=user, auto_id=get_auto_id(Customer),
                    )
                profile_fields = {
                    'name': name, 'phone': phone, 'customer_type': customer_type,
                    'whatsapp_number': (profile.get('whatsapp') or '').strip(),
                    'email': (profile.get('email') or '').strip(), 'state': state, 'city': city,
                    'tax_number': tax_number, 'tin_number': tin_number, 'pan_number': pan_number,
                    'country': branch.company.country.name if branch.company.country_id else '',
                }
                for field, value in profile_fields.items():
                    if not getattr(customer, field) and value:
                        setattr(customer, field, value)
                customer.save()

                vehicle = None
                plate_key = normalized(plate)
                for candidate in CustomerVehicle.objects.filter(customer=customer, is_deleted=False).only('id', 'vehicle_number'):
                    if normalized(candidate.vehicle_number) == plate_key:
                        vehicle = CustomerVehicle.objects.select_for_update().get(id=candidate.id)
                        break
                color = VehicleColor.objects.filter(id=vehicle_data.get('color_id'), is_deleted=False).first() if vehicle_data.get('color_id') else None
                emission = EmissionStandard.objects.filter(id=vehicle_data.get('emission_standard_id'), is_deleted=False).first() if vehicle_data.get('emission_standard_id') else None
                fuel = vehicle_data.get('fuel_type') or ''
                wheel = vehicle_data.get('wheel_type') or CustomerVehicle.WHEEL_TYPE_NORMAL
                if wheel not in dict(CustomerVehicle.WHEEL_TYPE_CHOICES):
                    wheel = CustomerVehicle.WHEEL_TYPE_NORMAL
                if vehicle is None:
                    vehicle = CustomerVehicle.objects.create(
                        customer=customer, vehicle_number=plate, vehicle_type=segment.vehicle_type,
                        vehicle_type_model=segment, make=make, brand_model=brand_model,
                        color=color, emission_standard=emission, fuel_type=fuel, wheel_type=wheel,
                        creator=user, auto_id=get_auto_id(CustomerVehicle),
                    )
                else:
                    for field, value in {'vehicle_type': segment.vehicle_type, 'vehicle_type_model': segment, 'make': make, 'brand_model': brand_model, 'color': color, 'emission_standard': emission, 'fuel_type': fuel, 'wheel_type': wheel}.items():
                        if not getattr(vehicle, f'{field}_id', None) and value:
                            setattr(vehicle, field, value)
                    vehicle.save()
        else:
            customer = Customer.objects.get(id=data.get('customer_id'), company=company, is_deleted=False)
            vehicle = CustomerVehicle.objects.get(id=data.get('vehicle_id'), customer=customer, is_deleted=False)
            if customer.branch_id != branch.id:
                return JsonResponse({'success': False, 'message': 'Customer is outside your branch'}, status=403)
        revised_from = None
        if data.get('revision_of_id'):
            revised_from = JobQuotation.objects.get(id=data['revision_of_id'], customer__company=company, is_deleted=False)
            if revised_from.customer_id != customer.id or revised_from.vehicle_id != vehicle.id:
                transaction.set_rollback(True)
                return JsonResponse({'success': False, 'message': 'Revision customer/vehicle mismatch'}, status=400)
            if branch and revised_from.branch_id != branch.id:
                transaction.set_rollback(True)
                return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
            lead = lead or revised_from.lead
        with transaction.atomic():
            quotation = JobQuotation.objects.create(
                quotation_number=f'JQT-{get_auto_id(JobQuotation):04d}', lead=lead, revised_from=revised_from,
                customer=customer, vehicle=vehicle, branch=branch or customer.branch,
                customer_comments=data.get('customer_comments') or '',
                additional_services=data.get('additional_services') or '', additional_days_needed=int(data.get('additional_days_needed') or 0),
                subtotal=Decimal(str(data.get('subtotal') or 0)), tax_percentage=Decimal(str(data.get('tax_percentage') or 0)),
                tax_amount=Decimal(str(data.get('tax_amount') or 0)), discount=Decimal(str(data.get('discount') or 0)),
                discount_type=data.get('discount_type') or 'amount', discount_percentage=Decimal(str(data.get('discount_percentage') or 0)),
                grand_total=Decimal(str(data.get('grand_total') or 0)), is_grand_total=bool(data.get('is_grand_total', True)),
                auto_id=get_auto_id(JobQuotation), creator=user,
            )
            for row in data.get('items', []):
                service = Service.objects.filter(id=row.get('service_id')).first() if row.get('service_id') else None
                stock = Stock.objects.filter(id=row.get('stock_item_id')).first() if row.get('stock_item_id') else None
                JobQuotationItem.objects.create(
                    quotation=quotation, service=service, service_name=row.get('service_name') or (service.name if service else ''),
                    stock_item=stock, stock_item_name=row.get('stock_item_name') or (stock.item_name if stock else ''),
                    warranty_years=Decimal(str(row.get('warranty_years') or 0)), rate=Decimal(str(row.get('rate') or 0)),
                    free_topup=row.get('free_topup') or '', quantity=Decimal(str(row.get('quantity', row.get('qty', 1)) or 1)),
                    auto_id=get_auto_id(JobQuotationItem), creator=user,
                )
            for row in data.get('extras', []):
                price, quantity = Decimal(str(row.get('price') or 0)), Decimal(str(row.get('quantity', row.get('qty', 1)) or 1))
                discount = Decimal(str(row.get('discount') or 0))
                if row.get('discount_type') == 'percentage':
                    discount = price * quantity * Decimal(str(row.get('discount_percentage') or 0)) / Decimal('100')
                total = Decimal(str(row['total'])) if row.get('total') is not None else max(Decimal('0'), price * quantity - discount)
                JobQuotationExtra.objects.create(
                    quotation=quotation, name=row.get('name') or '', price=price, quantity=quantity, discount=discount,
                    discount_type=row.get('discount_type') or 'amount', discount_percentage=Decimal(str(row.get('discount_percentage') or 0)),
                    total=total, remarks=row.get('remarks') or '', auto_id=get_auto_id(JobQuotationExtra), creator=user,
                )
            for index, (category, issue_service, issue, issue_text, photos) in enumerate(prepared_issues):
                reported_issue = JobQuotationIssue.objects.create(
                    quotation=quotation, category=category, service=issue_service, issue=issue,
                    issue_text=issue_text, sort_order=index, auto_id=get_auto_id(JobQuotationIssue), creator=user,
                )
                for photo_index, photo in enumerate(photos):
                    photo_record = JobQuotationIssuePhoto(
                        reported_issue=reported_issue, sort_order=photo_index,
                        auto_id=get_auto_id(JobQuotationIssuePhoto), creator=user,
                    )
                    photo_record.image.save(photo.name, photo, save=False)
                    stored_image_names.append(photo_record.image.name)
                    photo_record.save()
            if lead:
                lead.status = JobLead.STATUS_QUOTED
                lead.save(update_fields=['status', 'date_updated'])
                JobLeadFollowUp.objects.create(lead=lead, remarks=f'Quotation {quotation.quotation_number} created', status=JobLead.STATUS_QUOTED, auto_id=get_auto_id(JobLeadFollowUp), creator=user)
        return JsonResponse({'success': True, 'quotation_id': str(quotation.id), 'quotation_number': quotation.quotation_number})
    except (Customer.DoesNotExist, CustomerVehicle.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'Customer or vehicle not found'}, status=404)
    except Exception as exc:
        transaction.set_rollback(True)
        from django.core.files.storage import default_storage
        for image_name in stored_image_names:
            default_storage.delete(image_name)
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


def _job_quotation_data(quotation, include_lines=False, request=None):
    try:
        linked_job = quotation.job_card
        linked_job_id = str(linked_job.id)
    except Exception:
        linked_job_id = ''
    data = {
        'id': str(quotation.id), 'quotation_number': quotation.quotation_number,
        'customer_name': quotation.customer.name, 'customer_phone': quotation.customer.phone or '',
        'vehicle_number': quotation.vehicle.vehicle_number, 'branch_name': quotation.branch.name if quotation.branch else '',
        'grand_total': float(quotation.grand_total or 0), 'lead_id': str(quotation.lead_id) if quotation.lead_id else '',
        'is_accepted': quotation.is_accepted, 'revision_of_id': str(quotation.revised_from_id) if quotation.revised_from_id else '',
        'revision_count': quotation.revisions.filter(is_deleted=False).count(),
        'job_card_id': linked_job_id,
        'created_at': quotation.date_added.isoformat() if quotation.date_added else '',
        'date': quotation.date_added.date().isoformat() if quotation.date_added else '',
        'customer_comments': quotation.customer_comments or '',
    }
    if include_lines:
        data.update({
            'customer_id': str(quotation.customer_id), 'vehicle_id': str(quotation.vehicle_id),
            'customer_pan_number': quotation.customer.pan_number or '',
            'additional_services': quotation.additional_services or '', 'additional_days_needed': quotation.additional_days_needed,
            'subtotal': float(quotation.subtotal), 'tax_percentage': float(quotation.tax_percentage), 'tax_amount': float(quotation.tax_amount),
            'discount': float(quotation.discount), 'discount_type': quotation.discount_type,
            'discount_percentage': float(quotation.discount_percentage), 'is_grand_total': quotation.is_grand_total,
            'items': [{'service_id': str(i.service_id) if i.service_id else '', 'service_name': i.service_name, 'stock_item_id': str(i.stock_item_id) if i.stock_item_id else '', 'stock_item_name': i.stock_item_name or '', 'warranty_years': float(i.warranty_years), 'rate': float(i.rate), 'quantity': float(i.quantity), 'free_topup': i.free_topup or ''} for i in quotation.items.filter(is_deleted=False)],
            'extras': [{'name': e.name, 'price': float(e.price), 'quantity': float(e.quantity), 'discount': float(e.discount), 'discount_type': e.discount_type, 'discount_percentage': float(e.discount_percentage), 'total': float(e.total), 'remarks': e.remarks or ''} for e in quotation.extras.filter(is_deleted=False)],
            'reported_issues': [{
                'id': str(item.id), 'category_id': str(item.category_id), 'category_name': item.category.name,
                'service_id': str(item.service_id), 'service_name': item.service.name,
                'issue_id': str(item.issue_id or ''), 'issue_text': item.issue_text,
                'photos': [request.build_absolute_uri(photo.image.url) if request else photo.image.url for photo in item.photos.filter(is_deleted=False).order_by('sort_order')],
            } for item in quotation.reported_issues.filter(is_deleted=False).select_related('category', 'service', 'issue').prefetch_related('photos')],
        })
    return data


@csrf_exempt
def api_job_quotations(request):
    from .models import JobQuotation
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    qs = JobQuotation.objects.filter(is_deleted=False, customer__company=company).select_related('customer', 'vehicle', 'branch', 'lead').order_by('-date_added')
    if branch:
        qs = qs.filter(branch=branch)
    return JsonResponse({'success': True, 'quotations': [_job_quotation_data(q) for q in qs]})


@csrf_exempt
def api_job_quotation_detail(request, quotation_id):
    from .models import JobQuotation
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    quotation = JobQuotation.objects.filter(id=quotation_id, customer__company=company, is_deleted=False).select_related('customer', 'vehicle', 'branch', 'lead').first()
    if not quotation or (branch and quotation.branch_id != branch.id):
        return JsonResponse({'success': False, 'message': 'Quotation not found'}, status=404)
    return JsonResponse({'success': True, 'quotation': _job_quotation_data(quotation, True, request)})


@csrf_exempt
def api_job_quotation_update(request, quotation_id):
    from decimal import Decimal
    from django.db import transaction
    from client_management.models import Stock
    from service_management.models import Service
    from core.functions import get_auto_id
    from .models import JobQuotation, JobQuotationItem, JobQuotationExtra
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    quotation = JobQuotation.objects.filter(id=quotation_id, customer__company=company, is_deleted=False).first()
    if not quotation or (branch and quotation.branch_id != branch.id):
        return JsonResponse({'success': False, 'message': 'Quotation not found'}, status=404)
    if quotation.is_accepted:
        return JsonResponse({'success': False, 'message': 'Accepted quotations cannot be edited; create a revision'}, status=409)
    try:
        data = json.loads(request.body or '{}')
        with transaction.atomic():
            for field in ('additional_services', 'additional_days_needed', 'subtotal', 'tax_percentage', 'tax_amount', 'discount', 'discount_type', 'discount_percentage', 'grand_total', 'is_grand_total'):
                if field in data:
                    setattr(quotation, field, data[field])
            quotation.save()
            quotation.items.all().delete()
            quotation.extras.all().delete()
            for row in data.get('items', []):
                service = Service.objects.filter(id=row.get('service_id')).first() if row.get('service_id') else None
                stock = Stock.objects.filter(id=row.get('stock_item_id')).first() if row.get('stock_item_id') else None
                JobQuotationItem.objects.create(quotation=quotation, service=service,
                    service_name=row.get('service_name') or (service.name if service else ''), stock_item=stock,
                    stock_item_name=row.get('stock_item_name') or (stock.item_name if stock else ''),
                    warranty_years=Decimal(str(row.get('warranty_years') or 0)), rate=Decimal(str(row.get('rate') or 0)),
                    free_topup=row.get('free_topup') or '', quantity=Decimal(str(row.get('quantity', row.get('qty', 1)) or 1)),
                    auto_id=get_auto_id(JobQuotationItem), creator=user)
            for row in data.get('extras', []):
                price, quantity = Decimal(str(row.get('price') or 0)), Decimal(str(row.get('quantity', row.get('qty', 1)) or 1))
                discount = Decimal(str(row.get('discount') or 0))
                if row.get('discount_type') == 'percentage':
                    discount = price * quantity * Decimal(str(row.get('discount_percentage') or 0)) / Decimal('100')
                total = Decimal(str(row['total'])) if row.get('total') is not None else max(Decimal('0'), price * quantity - discount)
                JobQuotationExtra.objects.create(quotation=quotation, name=row.get('name') or '', price=price,
                    quantity=quantity, discount=discount, discount_type=row.get('discount_type') or 'amount',
                    discount_percentage=Decimal(str(row.get('discount_percentage') or 0)), total=total,
                    remarks=row.get('remarks') or '', auto_id=get_auto_id(JobQuotationExtra), creator=user)
        return JsonResponse({'success': True, 'quotation_id': str(quotation.id)})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


@csrf_exempt
def api_accept_job_quotation(request, quotation_id):
    from django.utils import timezone
    from .models import JobQuotation, JobLead, JobLeadFollowUp
    from core.functions import get_auto_id
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    company, branch = _job_pipeline_scope(user)
    quotation = JobQuotation.objects.filter(id=quotation_id, customer__company=company, is_deleted=False).select_related('lead').first()
    if not quotation or (branch and quotation.branch_id != branch.id):
        return JsonResponse({'success': False, 'message': 'Quotation not found'}, status=404)
    has_priced_items = quotation.items.filter(is_deleted=False, rate__gt=0).exists() or quotation.extras.filter(is_deleted=False, total__gt=0).exists()
    if not has_priced_items:
        return JsonResponse({'success': False, 'message': 'A quotation needs at least one priced item before acceptance'}, status=409)
    if not quotation.is_accepted:
        quotation.is_accepted, quotation.accepted_at, quotation.accepted_by = True, timezone.now(), user
        quotation.save(update_fields=['is_accepted', 'accepted_at', 'accepted_by', 'date_updated'])
        if quotation.lead:
            lead = quotation.lead
            lead.status, lead.success_chance = JobLead.STATUS_SUCCESS, 100
            lead.save(update_fields=['status', 'success_chance', 'date_updated'])
            JobLeadFollowUp.objects.create(lead=lead, remarks=f'Quotation {quotation.quotation_number} accepted', status=JobLead.STATUS_SUCCESS, success_chance=100, auto_id=get_auto_id(JobLeadFollowUp), creator=user)
    return JsonResponse({'success': True, 'is_accepted': True})


@csrf_exempt
def api_job_card_from_job_quotation(request, quotation_id):
    from decimal import Decimal
    from django.db import transaction
    from .models import JobQuotation, JobCard, JobCardServiceItem, JobCardPartItem, JobCardExtraItem
    user = get_user_from_token(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    try:
        company, branch_admin = _job_pipeline_scope(user)
        with transaction.atomic():
            quote = JobQuotation.objects.select_for_update().select_related('customer', 'vehicle', 'branch').filter(
                id=quotation_id, is_deleted=False, customer__company=company
            ).first()
            if not quote:
                return JsonResponse({'success': False, 'message': 'Job quotation not found'}, status=404)
            if branch_admin and quote.branch_id != branch_admin.id:
                return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
            if not quote.is_accepted:
                return JsonResponse({'success': False, 'message': 'Accept the quotation before conversion'}, status=409)
            has_priced_items = quote.items.filter(is_deleted=False, rate__gt=0).exists() or quote.extras.filter(is_deleted=False, total__gt=0).exists()
            if not has_priced_items:
                return JsonResponse({'success': False, 'message': 'A quotation needs at least one priced item before conversion'}, status=409)
            existing = JobCard.objects.filter(job_quotation=quote).first()
            if existing:
                return JsonResponse({'success': True, 'already_converted': True, 'job_card_id': str(existing.id), 'job_number': existing.job_number})
            branch = quote.branch or quote.customer.branch
            if not branch:
                return JsonResponse({'success': False, 'message': 'Quotation has no branch'}, status=400)
            items = list(quote.items.filter(is_deleted=False).select_related('service', 'stock_item'))
            job = JobCard.objects.create(
                company=company, branch=branch, customer=quote.customer, vehicle=quote.vehicle,
                job_quotation=quote, current_section='General Inspection',
                current_service=items[0].service_name if items else '',
                additional_remarks=quote.additional_services or None, creator=user,
            )
            for item in items:
                qty = item.quantity or Decimal('1')
                total = item.rate * qty
                if item.stock_item_id:
                    stock = item.stock_item
                    JobCardPartItem.objects.create(
                        job_card=job, stock_item=stock,
                        part_number=stock.part_number if stock else None,
                        alternate_part_number=stock.alternate_part_number if stock else None,
                        product_code=stock.barcode if stock else None,
                        product_name=item.stock_item_name or (stock.item_name if stock else 'Part'),
                        current_stock=stock.quantity if stock else 0, unit=stock.unit if stock else 'Pcs',
                        rate=item.rate, rate_with_tax=item.rate, quantity=qty, total_amount=total, creator=user,
                    )
                else:
                    JobCardServiceItem.objects.create(
                        job_card=job, service=item.service,
                        service_name=item.service_name or (item.service.name if item.service else 'Service'),
                        quantity=qty, unit='Unit', rate=item.rate, total_amount=total,
                        warranty=str(item.warranty_years or ''), warranty_period='years' if item.warranty_years else '',
                        remarks=f'Free top-up: {item.free_topup}' if item.free_topup else '', creator=user,
                    )
            for extra in quote.extras.filter(is_deleted=False):
                JobCardExtraItem.objects.create(
                    job_card=job, extra_details=extra.name, quantity=extra.quantity or Decimal('1'), rate=extra.price,
                    discount=extra.discount, discount_type=extra.discount_type,
                    discount_percentage=extra.discount_percentage, total_amount=extra.total,
                    remarks=extra.remarks or '', creator=user,
                )
            job.estimated_cost = quote.grand_total
            job.save(update_fields=['estimated_cost', 'date_updated'])
        return JsonResponse({'success': True, 'already_converted': False, 'job_card_id': str(job.id), 'job_number': job.job_number})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


