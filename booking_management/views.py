from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Booking


@login_required
def booking_list(request):
    user = request.user
    role = user.profile.role.name if hasattr(user, 'profile') and user.profile.role else None

    bookings = Booking.objects.filter(is_deleted=False).select_related(
        'customer', 'vehicle', 'vehicle__vehicle_type_model', 'branch'
    ).order_by('-booking_date', '-auto_id')

    if role == 'COMPANY_ADMIN' and hasattr(user.profile, 'company') and user.profile.company:
        bookings = bookings.filter(branch__company=user.profile.company)
    elif role == 'BRANCH_ADMIN' and hasattr(user, 'managed_branch'):
        bookings = bookings.filter(branch=user.managed_branch)

    search = request.GET.get('search', '').strip()
    if search:
        bookings = bookings.filter(
            Q(customer__name__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search) |
            Q(customer__phone__icontains=search)
        )

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    return render(request, 'booking/list.html', {
        'bookings': bookings,
        'search': search,
        'status_filter': status_filter,
        'title': 'Bookings',
    })
