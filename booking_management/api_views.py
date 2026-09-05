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

        # Fallback between wheelalignment/wheelbalancing and servicesreminder/reminderservice/servicereminder if template not found on Wawy portal
        if "Template or Sender Not Found" in result:
            alt_names = []
            if template_name.lower() == 'wheelalignment':
                alt_names = ['wheelbalancing']
            elif template_name.lower() == 'wheelbalancing':
                alt_names = ['wheelalignment']
            elif template_name.lower() in ['servicesreminder', 'reminderservice', 'servicereminder']:
                alt_names = [name for name in ['servicesreminder', 'reminderservice', 'servicereminder'] if name != template_name.lower()]

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
        
        # Check if using the official/template API
        if setting.is_official_api:
            from booking_management.api_views import send_whatsapp_template
            # The 'ready' template expects: {{1}} = Customer Name, {{2}} = Vehicle Number
            send_whatsapp_template(
                to_number=phone,
                template_name='ready',
                values=[name, vehicle_number],
                setting=setting
            )
        else:
            message = f"Hello {name}, your vehicle ({vehicle_number}) is ready for pickup! Thank you for choosing our service."
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
        default_msg = f"Hello {{customer_name}}, your vehicle ({{vehicle_number}}) is ready for pickup! Thank you for choosing our service."
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
        default_msg = f"Hello {{customer_name}}, thank you for choosing {{branch_name}}. Welcome to our service! We are delighted to have you and your vehicle ({{vehicle_number}}) with us."
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
                # Official Meta template: 'welcoming'
                threading.Thread(
                    target=send_whatsapp_template,
                    args=(cleaned_phone, 'welcoming', [customer_name, branch_name, vehicle_number]),
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
        default_msg = f"Hello {{customer_name}}, thank you for choosing {{branch_name}}! We look forward to serving you again. Have a great day!"
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

        first_svc_item = plan.invoice.items.filter(service__isnull=False).first() if plan.invoice else None
        if plan.reminder and plan.reminder.service:
            service_name = plan.reminder.service.name
        elif first_svc_item:
            service_name = first_svc_item.service_name or (first_svc_item.service.name if first_svc_item.service else '')
        else:
            service_name = plan.template_name or "Service Reminder"

        if plan.reminder and plan.reminder.service and plan.reminder.service.service_type:
            service_category = plan.reminder.service.service_type.slug
        elif first_svc_item and first_svc_item.service and first_svc_item.service.service_type:
            service_category = first_svc_item.service.service_type.slug
        else:
            service_category = ""

        formatted_date = plan.scheduled_date.strftime("%d-%m-%Y") if plan.scheduled_date else ""
        
        next_oil_change_km = None
        for item in plan.invoice.items.all():
            if hasattr(item, 'service_detail') and item.service_detail:
                if item.service_detail.service_category == 'oil_change' or item.service_detail.next_oil_change_km:
                    service_category = 'oil_change'
                    if item.service_detail.next_oil_change_km:
                        next_oil_change_km = item.service_detail.next_oil_change_km

        if service_category == 'oil_change':
            message = f"Dear {customer_name} your vehicle no {vehicle_no} next oil change to be done on {next_oil_change_km or 'N/A'} km"
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
            'next_oil_change_km': next_oil_change_km,
            'scheduled_date': str(plan.scheduled_date),
            'formatted_date': formatted_date,
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

            if is_oil:
                tmpl_name = 'oilreminder'
                tmpl_values = [customer_name, vehicle_no, next_km or "N/A"]
                message = f"Dear {customer_name} your vehicle no {vehicle_no} next oil change to be done on {next_km or 'N/A'} km"
            elif is_smoke:
                tmpl_name = (plan.template_name or (reminder.template_name if reminder else 'smoketest')).strip()
                tmpl_values = [customer_name, vehicle_no, formatted_date]
            elif is_wheel:
                # Always force 'wheelalignment' template for wheel alignment/balancing services.
                # DB stores 'servicereminder' as default — never use that for wheel services.
                tmpl_name = 'wheelalignment'
                # wheelalignment Wawy template: {{1}}=customer_name, {{2}}=vehicle_no, {{3}}=next_alignment_km, {{4}}=branch_name
                branch_name = plan.branch.name if (plan and plan.branch) else (invoice.branch.name if (invoice and invoice.branch) else 'Mobiz Auto Care')
                # Resolve next alignment KM from invoice service_detail or vehicle
                next_alignment_km = 'N/A'
                for _item in invoice.items.all():
                    if hasattr(_item, 'service_detail') and _item.service_detail and _item.service_detail.next_alignment_km:
                        next_alignment_km = str(_item.service_detail.next_alignment_km)
                        break
                if next_alignment_km == 'N/A' and invoice.vehicle and invoice.vehicle.next_alignment_km:
                    next_alignment_km = str(invoice.vehicle.next_alignment_km)
                tmpl_values = [customer_name, vehicle_no, next_alignment_km, branch_name]
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

        message_text = f"Dear {customer_name} your vehicle no {vehicle_number} next oil change to be done on {next_oil_change_km} km"
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

