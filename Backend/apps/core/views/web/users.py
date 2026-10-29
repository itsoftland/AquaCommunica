import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from ...permissions import CanDeleteUser
from ...services.get_usr_profile import get_user
from ...services.users import user_list
from ...models.customuser import CustomUser
from ...serializers.users import ChangePasswordSerializer, CustomUserListSerializer
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


class ListUsers(APIView):

    permission_classes = [IsAuthenticated, ]

    def get(self, request):

        user = request.user

        users = user_list(user).select_related('dealer', 'created_by')

        serializer = CustomUserListSerializer(
            users,
            many=True
        )

        return success_response(
            message="Users fetched successfully",
            data=serializer.data,
            status=status.HTTP_200_OK,
        )

