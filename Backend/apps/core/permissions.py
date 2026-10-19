from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied


class CanDeleteUser(BasePermission):
    """
    Controls which user roles can delete other user roles.
    """

    DELETE_RULES = {
        "superadmin": [
            "superadmin",
            "executive",
            "dealer",
            "production",
            "user_admin",
            "parent_user",
            "child_user",
        ],
        "dealer": ["user_admin"],
        "user_admin": ["parent_user", "child_user"],
    }

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        allowed_roles = self.DELETE_RULES.get(
            request.user.role, []
        )

        if obj.role not in allowed_roles:
            raise PermissionDenied(
                "You do not have permission to delete this user."
            )

        return True