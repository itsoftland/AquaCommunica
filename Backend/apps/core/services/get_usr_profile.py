import logging

from rest_framework.exceptions import PermissionDenied

from ..models.profiles import UserProfile, CustomUser


action_log = logging.getLogger('aquacommunica.action.log')


def get_user_profile(pk):
    """Retrieve a user profile by its primary key.

    Raises ``UserProfile.DoesNotExist`` if no matching profile exists.
    """
    user_profile = UserProfile.objects.get(pk=pk)
    return user_profile
   

def get_user(pk):

    user = CustomUser.objects.get(pk=pk)
    return user


def get_user_profiles_list(user):

    roles = [
        CustomUser.Role.SUPERADMIN,
        CustomUser.Role.DEALER,
        CustomUser.Role.EXECUTIVE,
    ]

    if user.role in roles:

        user_created_profiles = UserProfile.objects.filter(
            created_by=user
        )

        return user_created_profiles

    action_log.warning(
        f"User profile list denied: requested_by={user.id}, role={user.role}"
    )

    raise PermissionDenied("You do not have permission to view user profiles.")
