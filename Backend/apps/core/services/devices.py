import logging

from ..models.device import Devices, AllocationStatus
from ..utlis.device import clean_serial_numbers
from ..models.customuser import CustomUser

from rest_framework.exceptions import PermissionDenied, ValidationError


action_log = logging.getLogger('aquacommunica.action.log')

DEALER = CustomUser.Role.DEALER


def get_all_devices(request):

    user = request.user

    base_qs = Devices.objects.select_related(
        'user_profile',
        'dealer_profile',
        'created_by',
    )

    if user.is_superadmin:
        action_log.info(f"Listing all devices as superadmin: requested_by={user.id}")
        return base_qs

    if user.is_executive:
        action_log.info(
            f"Listing created devices: requested_by={user.id}, role={user.role}"
        )
        return base_qs.filter(created_by=user)

    if user.is_dealer:
        action_log.info(f"Listing dealer devices: requested_by={user.id}")
        return base_qs.filter(dealer_profile__user=user)

    if user.is_user_admin:
        action_log.info(f"Listing customer devices: requested_by={user.id}")
        return base_qs.filter(user_profile__user=user)

    action_log.warning(
        f"Device list denied: requested_by={user.id}, role={user.role}"
    )

    raise PermissionDenied("You do not have permission to list devices.")



def get_serial_numbers_from_request(request):

    serial_numbers = request.data.get("serial_number")

    if not isinstance(serial_numbers, list) or not serial_numbers:
    
        raise ValidationError({
            "message": "serial_number must be a non-empty list"
        })

    serial_numbers = clean_serial_numbers(serial_numbers)

    if not serial_numbers:
        raise ValidationError({
            "message": "Please provide valid serial numbers"
        })

    return serial_numbers


def get_customer_id_from_request(request):

    customer_id = request.data.get("customer_id")

    if not customer_id:
        raise ValidationError({
            "message": "customer_id is required"
        })

    return customer_id


def get_available_devices(user):

    if user.role == DEALER:
    
        available_devices = Devices.objects.filter(
            dealer_profile=user.dealer_profile,
            user_profile__isnull=True,
            allocation_status=AllocationStatus.DEALER,
        )

    else:

        available_devices = Devices.objects.filter(
            dealer_profile__isnull=True,
            user_profile__isnull=True,
            allocation_status=AllocationStatus.STOCK,
        )   

    return available_devices