import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from client_management.api_views import get_user_from_token
from client_management.models import Customer, CustomerVehicle, Scheme
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

        from core.functions import get_auto_id
        booking = Booking.objects.create(
            customer=customer,
            vehicle=vehicle,
            branch=customer.branch,
            booking_date=booking_date,
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
                'name': b.customer.name,
                'phone': b.customer.phone,
            },
            'vehicle': {
                'number': b.vehicle.vehicle_number,
                'model': b.vehicle.vehicle_type_model.name if b.vehicle.vehicle_type_model else '',
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

