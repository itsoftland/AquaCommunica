import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ...services.get_usr_profile import get_user_profile
from ...services.get_dlr_profile import get_dealer_profile
from ...models.profiles import UserProfile, DealerProfile
from ...utlis.responses import error_response, success_response
from ...permissions import CanManageUserProfiles, IsSuperAdmin
from ...serializers.profile import UserProfileUpdateSerializer, DealerProfileUpdateSerializer


action_log = logging.getLogger('aquacommunica.action.log')


class UpdateUserProfile(APIView):

    permission_classes = [IsAuthenticated, CanManageUserProfiles, ]

    def patch(self, request, pk):

        try:
            user_profile = get_user_profile(pk)
        except UserProfile.DoesNotExist:

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
            serializer.save()

            return success_response(
                message="User profile updated successfully.",
                data=serializer.data,
                status=status.HTTP_200_OK,
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

            return error_response(
                f"Dealer Profile with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DealerProfileUpdateSerializer(
            dealer_profile,
            data=request.data
        )

        if serializer.is_valid():
            serializer.save()

            return success_response(
                message="Dealer profile updated successfully.",
                data=serializer.data,
                status=status.HTTP_200_OK,
            )

        return error_response(
            message="Failed to update dealer profile.",
            data=serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )