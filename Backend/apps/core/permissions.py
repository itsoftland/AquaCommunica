from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied


class CanDeleteUser(BasePermission):
    """
    Controls which user roles can delete other users
    based on role and creator.
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
        return (
            request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        current_user = request.user

        # Get roles the current user can manage
        allowed_roles = self.DELETE_RULES.get(
            current_user.role, []
        )

        # Check target user's role
        if obj.role not in allowed_roles:
            raise PermissionDenied(
                "You do not have permission to manage this user."
            )

        # Superadmin can manage all allowed roles
        if current_user.role == "superadmin":
            return True

        # Dealer can manage only user admins created by that dealer
        if current_user.role == "dealer":
            if obj.created_by_id == current_user.id:
                return True

        # User Admin can manage only parents and children
        # created by that User Admin
        elif current_user.role == "user_admin":
            if obj.created_by_id == current_user.id:
                return True

        raise PermissionDenied(
            "You can manage only users created by you."
        )


class CanManageUserProfiles(BasePermission):
    """
    Superadmin can update any user.
    Dealer can update only user_admin accounts created by them.
    """
    def has_permission(self, request, view):
        user = request.user

        return (
            user.is_authenticated and
            user.role in ["superadmin", "dealer"]
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "superadmin":
            return True

        if user.role == "dealer":

            return (
                obj.created_by_id == user.id
            )

        raise PermissionDenied(
            "You dont have permission to update this profile"
        )