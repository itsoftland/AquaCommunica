import logging

from rest_framework.exceptions import PermissionDenied

from ..models.device import Devices


action_log = logging.getLogger('aquacommunica.action.log')


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
