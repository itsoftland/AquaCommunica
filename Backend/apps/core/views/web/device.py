import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from ...serializers.device import DeviceListSerializer
from ...utlis.responses import success_response, error_response
from ...pagination import CustomPagination
from ...models.customuser import CustomUser
from ...models.profiles import UserProfile
from ...models.device import Devices, AllocationStatus
from ...models.audit import AuditLog
from ...utlis.audit import record_audit
from ...services.devices import (
    get_all_devices, 
    get_serial_numbers_from_request,
    get_customer_id_from_request,
    get_available_devices
)
from ...permissions import IsSuperAdmin


action_log = logging.getLogger('aquacommunica.action.log')


class DeviceListingView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        devices = get_all_devices(request)

        params = request.query_params

        device_type = params.get("device_type")
        if device_type:
            devices = devices.filter(device_type=device_type)

        allocation_status = params.get("allocation_status")
        if allocation_status:
            devices = devices.filter(allocation_status=allocation_status)

        active = params.get("is_active")
        if active in ("true", "false"):
            devices = devices.filter(is_active=(active == "true"))

        search = params.get("search")
        if search:
            devices = devices.filter(serial_number__icontains=search)

        paginator = CustomPagination()

        paginated_devices = paginator.paginate_queryset(
            devices,
            request,
            view=self
        )

        serializer = DeviceListSerializer(paginated_devices, many=True)

        action_log.info(
            f"Devices listed: requested_by={request.user.id}, "
            f"count={len(paginated_devices)}, "
            f"page={params.get('page', 1)}"
        )

        return success_response(
            message="Devices fetched successfully",
            data={
                "count": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AssignDevicetoCustomer(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        DEALER = CustomUser.Role.DEALER
        SUPER_ADMIN = CustomUser.Role.SUPERADMIN
        EXECUTIVE = CustomUser.Role.EXECUTIVE

        user = request.user

        # --------------------------------------------------
        # 1. Permission validation
        # --------------------------------------------------

        if user.role not in [
            DEALER,
            EXECUTIVE,
            SUPER_ADMIN,
        ]:

            action_log.warning(
                "Assign device denied: user=%s role=%s",
                user.id,
                user.role,
            )

            return error_response(
                message="You don't have permission to assign devices to customers",
                status=status.HTTP_403_FORBIDDEN,
            )

        # --------------------------------------------------
        # 2. Get request data
        # --------------------------------------------------

        customer_id = get_customer_id_from_request(request)
        serial_numbers = get_serial_numbers_from_request(request)

        # --------------------------------------------------
        # 4. Start database transaction
        # --------------------------------------------------

        with transaction.atomic():

            # --------------------------------------------------
            # 5. Validate customer
            # --------------------------------------------------

            try:

                if user.role == DEALER:

                    customer = CustomUser.objects.select_related(
                        "dealer",
                    ).get(
                        id=customer_id,
                        dealer=user,
                    )

                else:

                    customer = CustomUser.objects.select_related(
                        "dealer",
                    ).get(
                        id=customer_id,
                        dealer__isnull=True,
                    )

            except CustomUser.DoesNotExist:

                action_log.warning(
                    "Assign device failed: customer not found "
                    "user=%s customer_id=%s",
                    user.id,
                    customer_id,
                )

                return error_response(
                    message="Customer not found",
                    status=status.HTTP_404_NOT_FOUND,
                )

            # --------------------------------------------------
            # 6. Get and lock customer profile
            # --------------------------------------------------

            try:

                customer_profile = customer.user_profile

                customer_profile = UserProfile.objects.select_for_update().get(
                    pk=customer_profile.pk
                )

            except (UserProfile.DoesNotExist, ObjectDoesNotExist):

                action_log.warning(
                    "Assign device failed: profile not found "
                    "user=%s customer=%s",
                    user.id,
                    customer.id,
                )

                return error_response(
                    message="Customer profile does not exist",
                    status=status.HTTP_404_NOT_FOUND,
                )

            # --------------------------------------------------
            # 7. Get available devices
            # --------------------------------------------------

            available_devices = get_available_devices(user)

            # --------------------------------------------------
            # 8. Lock requested available devices
            # --------------------------------------------------

            devices = list(
                available_devices.select_for_update().filter(
                    serial_number__in=serial_numbers
                )
            )

            available_serial_numbers = {
                device.serial_number
                for device in devices
            }

            invalid_serial_numbers = sorted(
                set(serial_numbers) - available_serial_numbers
            )

            if not devices:

                action_log.warning(
                    "Assign device failed: no available devices "
                    "user=%s customer=%s invalid=%s",
                    user.id,
                    customer.id,
                    invalid_serial_numbers,
                )

                return error_response(
                    message="None of the provided serial numbers are available for assignment",
                    data={
                        "invalid_serial_numbers": invalid_serial_numbers,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # --------------------------------------------------
            # 9. Validate customer device limit
            # --------------------------------------------------

            total_device_count = (
                customer_profile.total_device_count or 0
            )

            total_devices_using = Devices.objects.filter(
                user_profile=customer_profile,
            ).count()

            remaining_device_count = (
                total_device_count - total_devices_using
            )

            if remaining_device_count <= 0:

                action_log.warning(
                    "Assign device failed: device limit reached "
                    "user=%s customer=%s",
                    user.id,
                    customer.id,
                )

                return error_response(
                    message="Device limit reached. No remaining devices available for this customer.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if len(devices) > remaining_device_count:

                action_log.warning(
                    "Assign device failed: device limit exceeded "
                    "user=%s customer=%s remaining=%s requested=%s",
                    user.id,
                    customer.id,
                    remaining_device_count,
                    len(devices),
                )

                return error_response(
                    message=(
                        f"Device limit exceeded. Only "
                        f"{remaining_device_count} device(s) remaining "
                        f"for this customer, but {len(devices)} "
                        f"were requested."
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # --------------------------------------------------
            # 10. Assign devices
            # --------------------------------------------------

            assigned_serial_numbers = []

            for device in devices:

                old_values = {
                    "allocation_status": device.allocation_status,
                    "user_profile": device.user_profile_id,
                }

                device.user_profile = customer_profile
                device.is_active = True

                if user.role in [SUPER_ADMIN, EXECUTIVE]:

                    device.allocation_status = AllocationStatus.CUSTOMER

                elif user.role == DEALER:

                    # Keep dealer allocation status.
                    # Only link the customer profile.
                    pass

                device.save(
                    update_fields=[
                        "allocation_status",
                        "user_profile",
                        "is_active",
                    ]
                )

                # --------------------------------------------------
                # 11. Audit logging
                # --------------------------------------------------

                record_audit(
                    request,
                    AuditLog.Action.UPDATE,
                    user=user,
                    instance=device,
                    description=(
                        f"Device {device.serial_number} "
                        f"assigned to customer {customer.id}"
                    ),
                    old_values=old_values,
                    new_values={
                        "allocation_status": device.allocation_status,
                        "user_profile": device.user_profile_id,
                        "customer_id": customer.id,
                    },
                )

                assigned_serial_numbers.append(
                    device.serial_number
                )

            # --------------------------------------------------
            # 12. Calculate remaining device count
            # --------------------------------------------------

            assigned_serial_numbers.sort()

            remaining_device_count -= len(
                assigned_serial_numbers
            )

            # --------------------------------------------------
            # 13. Prepare response message
            # --------------------------------------------------

            message = (
                f"{len(assigned_serial_numbers)} device(s) "
                "assigned to customer successfully"
            )

            if invalid_serial_numbers:

                message += (
                    f". {len(invalid_serial_numbers)} "
                    "serial number(s) could not be assigned"
                )

            # --------------------------------------------------
            # 14. Action logging
            # --------------------------------------------------

            action_log.info(
                "User %s assigned %s device(s) to customer %s: %s",
                user.id,
                len(assigned_serial_numbers),
                customer.id,
                assigned_serial_numbers,
            )

            if invalid_serial_numbers:

                action_log.warning(
                    "Partial device assignment: user=%s "
                    "customer=%s invalid=%s",
                    user.id,
                    customer.id,
                    invalid_serial_numbers,
                )

            # --------------------------------------------------
            # 15. Success response
            # --------------------------------------------------

            return success_response(
                message=message,
                data={
                    "customer_id": customer.id,
                    "assigned_serial_numbers": assigned_serial_numbers,
                    "invalid_serial_numbers": invalid_serial_numbers,
                    "remaining_device_count": remaining_device_count,
                },
            )


class AssignDevicetoDealer(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def post(self):

        return success_response(
            message="haiii"
        )