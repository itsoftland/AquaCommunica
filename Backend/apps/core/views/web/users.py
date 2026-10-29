import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from ...permissions import CanDeleteUser
from ...services.get_usr_profile import get_user
from ...services.users import user_list
from ...models.customuser import CustomUser
from ...serializers.users import (
    AdminSetPasswordSerializer,
    ChangePasswordSerializer,
    CustomUserListSerializer,
)
from ...utlis.responses import error_response, success_response
from ...utlis.audit import record_audit
from ...models.audit import AuditLog


action_log = logging.getLogger('aquacommunica.action.log')


class PermanentUserDelete(APIView):

    permission_classes = [IsAuthenticated, CanDeleteUser, ]

    def delete(self, request, pk):

        try:
            user = get_user(pk)

            self.check_object_permissions(request, user)

            deleted_email = user.email
            deleted_role = user.role
            user.delete()

            record_audit(
                request,
                AuditLog.Action.DELETE,
                user=request.user,
                description=f"User {deleted_email} (id={pk}) permanently deleted",
                old_values={"id": pk, "email": deleted_email, "role": deleted_role},
            )

            action_log.info(
                f"User permanently deleted: id={pk}, email={deleted_email}, "
                f"deleted_by={request.user.id}"
            )

            return success_response(
                f"User permanently deleted successfully.",
                status=status.HTTP_200_OK,
            )

        except CustomUser.DoesNotExist:

            action_log.warning(
                f"Permanent delete failed, user not found: id={pk}, "
                f"requested_by={request.user.id}"
            )

            return error_response(
                f"User with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )


class SoftDeleteUser(APIView):

    permission_classes = [IsAuthenticated, CanDeleteUser, ]

    def patch(self, request, pk):

        try:
            user = get_user(pk)
        except CustomUser.DoesNotExist:

            action_log.warning(
                f"Soft delete failed, user not found: id={pk}, "
                f"requested_by={request.user.id}"
            )

            return error_response(
                f"User with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request, user)

        user.is_active = False
        user.save(update_fields=["is_active"])

        if user.role == "user_admin":
            profile = user.user_profile
            profile.is_profile_active = False
            profile.save(update_fields=["is_profile_active"])

        if user.role == "dealer":
            profile = user.dealer_profile
            profile.is_profile_active = False
            profile.save(update_fields=["is_profile_active"])

        record_audit(
            request,
            AuditLog.Action.UPDATE,
            user=request.user,
            instance=user,
            description=f"User {user.email} deactivated",
            old_values={"is_active": True},
            new_values={"is_active": False},
        )

        action_log.info(
            f"User deactivated: id={pk}, email={user.email}, role={user.role}, "
            f"deactivated_by={request.user.id}"
        )

        return success_response(
            "User deactivated successfully.",
            status=status.HTTP_200_OK,
        )


class RestoreUser(APIView):
    """Undo a soft delete by reactivating the user and their profile."""

    permission_classes = [IsAuthenticated, CanDeleteUser, ]

    def patch(self, request, pk):

        try:
            user = get_user(pk)
        except CustomUser.DoesNotExist:

            action_log.warning(
                f"Restore failed, user not found: id={pk}, "
                f"requested_by={request.user.id}"
            )

            return error_response(
                f"User with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request, user)

        if user.is_active:
            return error_response(
                "User is already active.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = True
        user.save(update_fields=["is_active"])

        if user.role == "user_admin":
            profile = user.user_profile
            profile.is_profile_active = True
            profile.save(update_fields=["is_profile_active"])

        if user.role == "dealer":
            profile = user.dealer_profile
            profile.is_profile_active = True
            profile.save(update_fields=["is_profile_active"])

        record_audit(
            request,
            AuditLog.Action.UPDATE,
            user=request.user,
            instance=user,
            description=f"User {user.email} restored",
            old_values={"is_active": False},
            new_values={"is_active": True},
        )

        action_log.info(
            f"User restored: id={pk}, email={user.email}, role={user.role}, "
            f"restored_by={request.user.id}"
        )

        return success_response(
            "User restored successfully.",
            status=status.HTTP_200_OK,
        )


class ChangePassword(APIView):

    permission_classes = [IsAuthenticated, ]

    def post(self, request):

        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request}
        )

        if not serializer.is_valid():

            action_log.warning(
                f"Password change failed, validation error: "
                f"user_id={request.user.id}, errors={list(serializer.errors.keys())}"
            )

            serializer.is_valid(raise_exception=True)

        serializer.save()

        record_audit(
            request,
            AuditLog.Action.UPDATE,
            user=request.user,
            instance=request.user,
            description=f"User {request.user.email} changed password",
        )

        action_log.info(
            f"Password changed: user_id={request.user.id}, "
            f"email={request.user.email}"
        )

        return success_response(
            message="Password changed sucessfully",
            status=status.HTTP_200_OK,
        )


class AdminChangeUserPassword(APIView):
    """Change another user's password without needing their current one."""

    permission_classes = [IsAuthenticated, CanDeleteUser, ]

    def post(self, request, pk):

        try:
            user = get_user(pk)
        except CustomUser.DoesNotExist:

            action_log.warning(
                f"Admin password change failed, user not found: id={pk}, "
                f"requested_by={request.user.id}"
            )

            return error_response(
                f"User with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request, user)

        serializer = AdminSetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        record_audit(
            request,
            AuditLog.Action.UPDATE,
            user=request.user,
            instance=user,
            description=f"Password for {user.email} changed by admin",
        )

        action_log.info(
            f"Admin changed user password: id={pk}, email={user.email}, "
            f"changed_by={request.user.id}"
        )

        return success_response(
            message="Password changed successfully",
            status=status.HTTP_200_OK,
        )


class ListUsers(APIView):

    permission_classes = [IsAuthenticated, ]

    def get(self, request):

        user = request.user

        users = user_list(user).select_related('dealer', 'created_by', 'user_profile')

        serializer = CustomUserListSerializer(
            users,
            many=True
        )

        return success_response(
            message="Users fetched successfully",
            data=serializer.data,
            status=status.HTTP_200_OK,
        )


