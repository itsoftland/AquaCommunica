import logging

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ...utlis.responses import success_response, error_response
from ...models.profiles import UserProfile
from ...services.license_server import register_with_license_server
from ...services.get_usr_profile import get_user_profile


log_license_server = logging.getLogger('aquacommunica.licenseserver')


class RegisterUserProfileWithLicenseServer(APIView):

    permission_classes = [IsAuthenticated,]
    
    def post(self, request, pk):

        log_license_server.info(f"User Profile registration started for id: {pk}")
        user = request.user

        try:
            user_profile = get_user_profile(pk)

        except UserProfile.DoesNotExist:
            log_license_server.info(f"User Profile not found for id: {pk}")
            return error_response(
                f"User Profile with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        if user_profile.profile_id:

            log_license_server.info(f"Registration process stoped - this profile already registered. profile ID: {user_profile.profile_id}")

            return error_response(
                f"User Profile with ID = {pk} is already registered with the license server",
                status=status.HTTP_409_CONFLICT,
            )

        log_license_server.info(f"Initiating registration for: {user_profile.contact_email}")

        registration_result = register_with_license_server(user_profile)

        if not registration_result['success']:
            log_license_server.info(f"Registration failed: {registration_result['error']}")
            return error_response(
                "License registration failed",
                data={"error": registration_result['error']},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


        user_profile.profile_id = registration_result['customer_id']
        user_profile.save()
        log_license_server.info(f"Saved Profile_id: {user_profile.profile_id} for profile: {user_profile.contact_email}")
        
        return success_response(
            f"Registered with license server successfully! Customer ID: {user_profile.profile_id}",
            data={"profile ID": user_profile.profile_id},
            status=status.HTTP_200_OK,
        )