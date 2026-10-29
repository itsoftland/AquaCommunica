import logging

from rest_framework.exceptions import PermissionDenied

from ..models.profiles import DealerProfile
from ..models.customuser import CustomUser


action_log = logging.getLogger('aquacommunica.action.log')


def get_dealer_profile(pk):
    """Retrieve a dealer profile by its primary key.

    Raises ``DealerProfile.DoesNotExist`` if no matching profile exists.
    """
    dealer_profile = DealerProfile.objects.get(pk=pk)
    return dealer_profile


def get_dealer_profiles_list(user):

    if user.role in CustomUser.Role.SUPERADMIN:

        user_created_profiles = DealerProfile.objects.filter(
            created_by=user
        )

        return user_created_profiles

    action_log.warning(
            f"Dealer profile list denied: requested_by={user.id}, role={user.role}"
        )
    
    raise PermissionDenied("You do not have permission to view dealer profiles.")