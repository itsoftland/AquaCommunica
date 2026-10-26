import logging

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.db import transaction

from ...utlis.responses import success_response, error_response
from ...models.profiles import UserProfile, DealerProfile
from ...services.license_server import register_with_license_server
from ...services.get_usr_profile import get_user_profile
from ...services.get_dlr_profile import get_dealer_profile
from ...permissions import LicensePermission
from ...task import poll_user_profile_license
from ...serializers.profile import UserProfileDisplaySerializer


log_license_server = logging.getLogger('aquacommunica.licenseserver')


class RegisterUserProfileWithLicenseServer(APIView):

    permission_classes = [IsAuthenticated, LicensePermission, ]
    
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



class RegisterDealerProfileWithLicenseServer(APIView):

    permission_classes = [IsAuthenticated, LicensePermission, ]

    def post(self, request, pk):

        log_license_server.info(f"Dealer Profile registration started for id: {pk}")
        user = request.user

        try:
            dealer_profile = get_dealer_profile(pk=pk)

        except DealerProfile.DoesNotExist:

            log_license_server.info(f"Dealer Profile not found for id: {pk}")
            return error_response(
                f"Dealer Profile with ID = {pk} not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        if dealer_profile.profile_id:
        
            log_license_server.info(f"Registration process stoped - this profile already registered. profile ID: {dealer_profile.profile_id}")

            return error_response(
                f"Dealer Profile with ID = {pk} is already registered with the license server",
                status=status.HTTP_409_CONFLICT,
            )


        log_license_server.info(f"Initiating registration for: {dealer_profile.contact_email}")
        
        registration_result = register_with_license_server(dealer_profile)

        if not registration_result['success']:
            log_license_server.info(f"Registration failed: {registration_result['error']}")
            return error_response(
                "License registration failed",
                data={"error": registration_result['error']},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


        dealer_profile.profile_id = registration_result['customer_id']
        dealer_profile.save()
        log_license_server.info(f"Saved Profile_id: {dealer_profile.profile_id} for profile: {dealer_profile.contact_email}")
        
        return success_response(
            f"Registered with license server successfully! Customer ID: {dealer_profile.profile_id}",
            data={"profile ID": dealer_profile.profile_id},
            status=status.HTTP_200_OK,
        )


class ValidateUserProfileLicense(APIView):

    permission_classes = [IsAuthenticated, LicensePermission, ]

    def post(self, request, pk):

        log_license_server.info(f"User Profile license validation started for id: {pk}")
        user = request.user

        with transaction.atomic():
            try:
                profile = UserProfile.objects.get(pk=pk)
            except UserProfile.DoesNotExist:
                log_license_server.info(f"User Profile not found for id: {pk}")
                return error_response(
                    message="user profile not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not profile.profile_id:
                log_license_server.warning(f"User Profile id: {pk} not registered with license server")
                return error_response(
                    message="Profile not registered with license server yet",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if profile.authentication_status == UserProfile.AuthStatus.VALIDATING:
                log_license_server.info(f"License validation already in progress for id: {pk}")
                return success_response(
                    message="License validation already in progress",
                    status=status.HTTP_200_OK,
                )

            profile.authentication_status = UserProfile.AuthStatus.VALIDATING
            profile.save()

            poll_user_profile_license.delay(profile.id)
            log_license_server.info(f"License validation task queued for id: {pk}")

            serializer = UserProfileDisplaySerializer(profile)

            return success_response(
                message="License validation started. This may take up to 2 minutes. Refresh to see updated status.",
                data=serializer.data,
                status=status.HTTP_200_OK,
            )


