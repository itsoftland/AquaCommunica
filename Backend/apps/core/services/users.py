import logging

from rest_framework.exceptions import PermissionDenied

from ..models.customuser import CustomUser


action_log = logging.getLogger('aquacommunica.action.log')


def user_list(user):

    executive  = CustomUser.Role.EXECUTIVE
    dealer     = CustomUser.Role.DEALER
    user_admin = CustomUser.Role.USER_ADMIN
    production = CustomUser.Role.PRODUCTION
    parent     = CustomUser.Role.PARENT_USER
    child      = CustomUser.Role.CHILD_USER

    if user.is_superadmin:

        action_log.info(f"Listing users as superadmin: requested_by={user.id}")

        user_list = CustomUser.objects.filter(
            role__in=[
                executive,
                dealer,
                user_admin,
                production,
            ],
            created_by=user,
        )

        return user_list

    if user.role in [
        executive,
        dealer,
    ]:

        action_log.info(
            f"Listing user admins: requested_by={user.id}, role={user.role}"
        )

        user_list = CustomUser.objects.filter(
            role=user_admin,
            created_by=user,
        )

        return user_list

    if user.is_user_admin:

        action_log.info(f"Listing parent/child users: requested_by={user.id}")

        user_list = CustomUser.objects.filter(
            role__in=[
                parent,
                child,
            ],
            created_by=user
        )

        return user_list

    action_log.warning(
        f"User list denied: requested_by={user.id}, role={user.role}"
    )

    raise PermissionDenied("You do not have permission to list user.")




