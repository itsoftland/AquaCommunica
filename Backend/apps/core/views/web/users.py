import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from ...permissions import CanDeleteUser
from ...services.get_usr_profile import get_user
from ...models.customuser import CustomUser
from ...serializers.users import ChangePasswordSerializer
from ...utlis.responses import error_response, success_response


action_log = logging.getLogger('aquacommunica.action.log')


class PermanentUserDelete(APIView):

    permission_classes = [IsAuthenticated, CanDeleteUser, ]

    def delete(self, request, pk):

        try:
            user = get_user(pk)

            self.check_object_permissions(request, user)
            
            user.delete()

            return success_response(
                f"User permanently deleted successfully.",
                status=status.HTTP_200_OK,
            )

        except CustomUser.DoesNotExist:

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

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return success_response(
            message="Password changed sucessfully",
            status=status.HTTP_200_OK,
        )
