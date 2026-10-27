import logging

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.db import transaction

from ...permissions import LicensePermission
from ...task import poll_user_profile_license
from ...services.get_usr_profile import get_user_profile
from ...models.profiles import UserProfile, DealerProfile
from ...services.get_dlr_profile import get_dealer_profile
from ...utlis.responses import success_response, error_response
from ...serializers.profile import UserProfileDisplaySerializer
from ...services.license_server import register_with_license_server, fetch_user_profile_from_license_server, _build_user_profile_sync_diff, _map_auth_status, _check_user_count_reduction
from ...services.license_server import _parse_license_date


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


class SyncUserProfileLicense(APIView):

    permission_classes = [
        IsAuthenticated, 
        LicensePermission
    ]

    def post(self, request, pk):

        user = request.user

        try:
            profile = UserProfile.objects.get(pk=pk)
        except UserProfile.DoesNotExist:

            return error_response(
                message="Profile not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        if profile.client_type == UserProfile.ClientType.DEALER:

            return error_response(
                message="License sync is not available for dealer-managed companies.",
                status=status.HTTP_400_BAD_REQUEST,
            )


        # Access Control
        if user.is_user_admin:

            if not user.user_profile or user.user_profile.id != profile.id:
                return error_response(
                    message="You can only sync your own profile.",
                    status=status.HTTP_403_FORBIDDEN,
                )

        elif user.is_executive:

            if profile.created_by_id != user.id:
                return error_response(
                    message="You can only sync profiles you created.",
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        elif user.is_dealer:

            if profile.created_by_id != user.id:
                return error_response(
                    message="You can only sync profiles you created.",
                    status=status.HTTP_403_FORBIDDEN,
                )

        elif not user.is_superadmin:

            return error_response(
                message="Not authorized.",
                status=status.HTTP_403_FORBIDDEN,
            )

        if not profile.profile_id:

            return error_response(
                message="Company is not registered with the license server yet.",
                status=status.HTTP_400_BAD_REQUEST,
            )


        result = fetch_user_profile_from_license_server(profile.profile_id)

        if not result['success']:

            return error_response(
                message="failed",
                data=result['error'],
                status=status.HTTP_502_BAD_GATEWAY
            )

        diff = _build_user_profile_sync_diff(profile, result['data'])

        return success_response(
            message="Sync preview ready.",
            data=diff,
            status=status.HTTP_200_OK,
        )


class SyncUserProfileLicenseConfirm(APIView):

    permission_classes = [
        IsAuthenticated,
        LicensePermission,
    ]

    def post(self, request, pk):

        user = request.user

        try:
            profile = UserProfile.objects.get(pk=pk)
        except UserProfile.DoesNotExist:

            return error_response(
                message="user profile not found",
                status=status.HTTP_404_NOT_FOUND,
            )

        if profile.client_type == UserProfile.ClientType.DEALER:

            return error_response(
                message="License sync is not available for dealer-managed profiles.",
                status=status.HTTP_400_BAD_REQUEST,
            )


        if user.is_user_admin:
        
            if not user.user_profile or user.user_profile.id != profile.id:
                return error_response(
                    message="You can only sync your own profile.",
                    status=status.HTTP_403_FORBIDDEN,
                )

        elif user.is_executive:

            if profile.created_by_id != user.id:
                return error_response(
                    message="You can only sync profiles you created.",
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        elif user.is_dealer:

            if profile.created_by_id != user.id:
                return error_response(
                    message="You can only sync profiles you created.",
                    status=status.HTTP_403_FORBIDDEN,
                )

        elif not user.is_superadmin:

            return error_response(
                message="Not authorized.",
                status=status.HTTP_403_FORBIDDEN,
            )


        result = fetch_user_profile_from_license_server(profile.profile_id)
        if not result['success']:
            return error_response(
                message="Failed to communicate with the external server.",
                data=result['error'],
                status=status.HTTP_502_BAD_GATEWAY,
            )

        auth_data = result['data']
        is_dealer_created_user_profile = profile.client_type == UserProfile.ClientType.DEALER

        if not is_dealer_created_user_profile:

            diff = _build_user_profile_sync_diff(profile, auth_data)

            if diff['error']:

                profile.authentication_status = UserProfile.AuthStatus.PENDING
                profile.error_message = diff["error"]
                profile.save(update_fields=['authentication_status', 'error_message'])

                return error_response(
                    message="Company consistency check failed.",
                    data=diff["error"],
                    status=status.HTTP_400_BAD_REQUEST,
                )

        def _si(val):
            try:
                return int(val or 0)
            except (ValueError, TypeError):
                return 0

        raw_from_date = auth_data.get('ProductFromDate')
        raw_to_date   = auth_data.get('ProductToDate')

        new_auth_status = _map_auth_status(
            auth_data.get('Authenticationstatus', ''),
            profile.authentication_status,
        )

        if not is_dealer_created_user_profile:

            new_total_user_count  = _si(auth_data.get('TotalUserCount'))
            new_parent_user_count = _si(auth_data.get('PremiumUserCount'))
            new_child_user_count  = _si(auth_data.get('IntermediateUserCount'))

            ok, errs = _check_user_count_reduction(profile, new_total_user_count, new_parent_user_count, new_child_user_count)

            if not ok:

                return error_response(
                    message="Cannot apply sync: would reduce user counts below current assignments.",
                    data=errs,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            profile.total_licence_unit = _si(auth_data.get('NumberOfLicence'))
            profile.total_device_count = _si(auth_data.get('PalmtecCount'))
            profile.total_user_count   = new_total_user_count
            profile.parent_user_count  = new_parent_user_count
            profile.child_user_count   = new_child_user_count

        profile.validity_from_date = _parse_license_date(raw_from_date) or profile.validity_from_date
        profile.validity_to_date   = _parse_license_date(raw_to_date) or profile.validity_to_date
        profile.authentication_status = new_auth_status

        if new_auth_status == UserProfile.AuthStatus.APPROVED:
            profile.is_profile_active = True

        profile.product_registration_id = _si(auth_data.get('ProductRegistrationId'))
        profile.unique_identifier = auth_data.get('UniqueIDentifier', '') or profile.unique_identifier
        profile.error_message = None

        profile.save()

        serializer = UserProfileDisplaySerializer(profile)

        return success_response(
            message="License data synced successfully.",
            data=serializer.data,
            status=status.HTTP_200_OK,
        )

    