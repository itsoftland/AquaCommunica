import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ...services.get_usr_profile import get_user_profile
from ...services.get_dlr_profile import get_dealer_profile
from ...models.profiles import UserProfile, DealerProfile
from ...utlis.responses import error_response, success_response
from ...utlis.audit import record_audit
from ...models.audit import AuditLog
from ...permissions import CanManageUserProfiles, IsSuperAdmin
from ...serializers.profile import UserProfileUpdateSerializer, DealerProfileUpdateSerializer


action_log = logging.getLogger('aquacommunica.action.log')


class UpdateUserProfile(APIView):

    permission_classes = [IsAuthenticated, CanManageUserProfiles, ]

    def patch(self, request, pk):

        try:
            user_profile = get_user_profile(pk)
        except UserProfile.DoesNotExist:

            action_log.warning(
                f"User profile update failed, profile not found: id={pk}, "
                f"requested_by={request.user.id}"
            )

            return error_response(
                f"User Profile with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request, user_profile)

        serializer = UserProfileUpdateSerializer(
            user_profile,
            data=request.data
        )

        if serializer.is_valid():
            old_values = {
                field: str(getattr(user_profile, field, None))
                for field in serializer.validated_data
            }
            serializer.save()

            record_audit(
                request,
                AuditLog.Action.UPDATE,
                user=request.user,
                instance=user_profile,
                description=f"User profile {pk} updated",
                old_values=old_values,
                new_values={
                    field: str(value)
                    for field, value in serializer.validated_data.items()
                },
            )

            action_log.info(
                f"User profile updated: id={pk}, "
                f"fields={list(serializer.validated_data.keys())}, "
                f"updated_by={request.user.id}"
            )

            return success_response(
                message="User profile updated successfully.",
                data=serializer.data,
                status=status.HTTP_200_OK,
            )

        action_log.warning(
            f"User profile update failed, validation error: id={pk}, "
            f"errors={list(serializer.errors.keys())}, updated_by={request.user.id}"
        )

        return error_response(
            message="Failed to update user profile.",
            data=serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class UpdateDealerProfile(APIView):

    permission_classes = [IsAuthenticated, IsSuperAdmin, ]

    def patch(self, request, pk):

        try:
            dealer_profile = get_dealer_profile(pk)
        except DealerProfile.DoesNotExist:

            action_log.warning(
                f"Dealer profile update failed, profile not found: id={pk}, "
                f"requested_by={request.user.id}"
            )

            return error_response(
                f"Dealer Profile with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DealerProfileUpdateSerializer(
            dealer_profile,
            data=request.data
        )

        if serializer.is_valid():
            old_values = {
                field: str(getattr(dealer_profile, field, None))
                for field in serializer.validated_data
            }
            serializer.save()

            record_audit(
                request,
                AuditLog.Action.UPDATE,
                user=request.user,
                instance=dealer_profile,
                description=f"Dealer profile {pk} updated",
                old_values=old_values,
                new_values={
                    field: str(value)
                    for field, value in serializer.validated_data.items()
                },
            )

            action_log.info(
                f"Dealer profile updated: id={pk}, "
                f"fields={list(serializer.validated_data.keys())}, "
                f"updated_by={request.user.id}"
            )

            return success_response(
                message="Dealer profile updated successfully.",
                data=serializer.data,
                status=status.HTTP_200_OK,
            )

        action_log.warning(
            f"Dealer profile update failed, validation error: id={pk}, "
            f"errors={list(serializer.errors.keys())}, updated_by={request.user.id}"
        )

        return error_response(
            message="Failed to update dealer profile.",
            data=serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )