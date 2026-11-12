import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from ...services.devices import get_all_devices
from ...serializers.device import DeviceListSerializer
from ...utlis.responses import success_response, error_response
from ...pagination import CustomPagination
from ...models.customuser import CustomUser
from ...models.profiles import UserProfile
from ...models.device import Devices, AllocationStatus
from ...models.audit import AuditLog
from ...utlis.audit import record_audit


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

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):

        DEALER = CustomUser.Role.DEALER
        SUPER_ADMIN = CustomUser.Role.SUPERADMIN
        EXECUTIVE = CustomUser.Role.EXECUTIVE

        user = request.user

        if user.role not in [
            DEALER,
            EXECUTIVE,
            SUPER_ADMIN,
        ]:

            action_log.warning(
                "Assign device denied: user=%s role=%s", user.id, user.role
            )
            return error_response(
                message="You dont have permisson to assign device to customer",
                status=status.HTTP_403_FORBIDDEN,
            )

        serial_numbers = request.data.get('serial_number')
        customer_id = request.data.get('customer_id')

        if not isinstance(serial_numbers, list) or not serial_numbers:
            action_log.warning(
                "Assign device failed (invalid serial_number payload): user=%s", user.id
            )
            return error_response(
                message="serial_numbers must be a non-empty list",
                status=status.HTTP_400_BAD_REQUEST,
            )

        # remove duplicate
        serial_numbers = list(set(
            sn.strip() for sn in serial_numbers
            if isinstance(sn, str) and sn.strip()
        ))

        if not serial_numbers:
            action_log.warning(
                "Assign device failed (no valid serial numbers): user=%s", user.id
            )
            return error_response(
                message="Please provide valid serial numbers",
                status=status.HTTP_400_BAD_REQUEST,
            )


        if user.role == DEALER:
            available_devices = Devices.objects.select_related(
                'user_profile',
                'dealer_profile',
                'created_by',
            ).filter(
                dealer_profile=user.dealer_profile,
                user_profile__isnull=True,
                allocation_status=AllocationStatus.DEALER
            )

            try:
                customer = CustomUser.objects.select_related(
                    'dealer',
                    'user_admin',
                    'created_by'
                ).get(
                    id=customer_id,
                    dealer=user
                )
    
            except CustomUser.DoesNotExist:
                action_log.warning(
                    "Assign device failed (customer not found): user=%s customer_id=%s",
                    user.id, customer_id
                )
                return error_response(
                    message="Customer not found",
                    status=status.HTTP_404_NOT_FOUND
                )

        if user.role in [SUPER_ADMIN, EXECUTIVE]:
            available_devices = Devices.objects.select_related(
                'user_profile',
                'dealer_profile',
                'created_by',
            ).filter(
                dealer_profile__isnull=True,
                user_profile__isnull=True,
                allocation_status=AllocationStatus.STOCK
            )

            try:
                customer = CustomUser.objects.select_related(
                    'dealer',
                    'user_admin',
                    'created_by'
                ).get(
                    id=customer_id,
                    dealer__isnull=True
                )
    
            except CustomUser.DoesNotExist:
                action_log.warning(
                    "Assign device failed (customer not found): user=%s customer_id=%s",
                    user.id, customer_id
                )
                return error_response(
                    message="Customer not found",
                    status=status.HTTP_404_NOT_FOUND
                )

        if not available_devices.exists():

            action_log.warning(
                "Assign device failed (no stock): user=%s", user.id
            )
            return error_response(
                message="No available devices in stock",
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            customer_profile = customer.user_profile

        except UserProfile.DoesNotExist:
            action_log.warning(
                "Assign device failed (no customer profile): user=%s customer=%s",
                user.id, customer.id
            )
            return error_response(
                message="Customer profile does not exist",
                status=status.HTTP_404_NOT_FOUND,
            )
        
        total_device_count = customer_profile.total_device_count
        total_devices_using = customer_profile.devices.count()

        remaning_device_count = total_device_count - total_devices_using

        if remaning_device_count == 0:

            action_log.warning(
                "Assign device failed (limit reached): user=%s customer=%s",
                user.id, customer.id
            )
            return error_response(
                message="Device limit reached. No remaining devices available for this customer.",
                status=status.HTTP_400_BAD_REQUEST
            )

        if remaning_device_count < len(serial_numbers):

            action_log.warning(
                "Assign device failed (limit exceeded): user=%s customer=%s "
                "remaining=%s requested=%s",
                user.id, customer.id, remaning_device_count, len(serial_numbers)
            )
            return error_response(
                message=(
                    f"Device limit exceeded. Only {remaning_device_count} "
                    f"device(s) remaining for this customer, but "
                    f"{len(serial_numbers)} were requested."
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        available_device_list = list(
            available_devices.filter(
                serial_number__in=serial_numbers
            )
        )

        available_serial_numbers = {
            device.serial_number for device in available_device_list
        }

        invalid_serial_numbers = list(
            set(serial_numbers) - available_serial_numbers
        )

        for sn in available_serial_numbers:

            device = Devices.objects.get(serial_number=sn)
            old_values = {
                "allocation_status": device.allocation_status,
                "user_profile": device.user_profile_id,
            }

            if user.role in [SUPER_ADMIN, EXECUTIVE]:
                device.allocation_status = AllocationStatus.CUSTOMER
                device.user_profile = customer_profile
                device.is_active = True

                device.save(update_fields=[
                    'allocation_status',
                    'user_profile',
                    'is_active'
                ])

            if user.role == DEALER:
                device.user_profile = customer_profile
                device.is_active = True

                device.save(update_fields=[
                    'user_profile',
                    'is_active'
                ])

            record_audit(
                request,
                AuditLog.Action.UPDATE,
                user=user,
                instance=device,
                description=f"Device {sn} assigned to customer {customer.id}",
                old_values=old_values,
                new_values={
                    "allocation_status": device.allocation_status,
                    "user_profile": device.user_profile_id,
                    "customer_id": customer.id,
                },
            )

        assigned_serial_numbers = sorted(available_serial_numbers)

        if not assigned_serial_numbers:
            action_log.warning(
                "Assign device failed (none available): user=%s customer=%s invalid=%s",
                user.id, customer.id, sorted(invalid_serial_numbers)
            )
            return error_response(
                message="None of the provided serial numbers are available for assignment",
                data={"invalid_serial_numbers": sorted(invalid_serial_numbers)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action_log.info(
            "User %s assigned %d device(s) to customer %s: %s",
            user.id,
            len(assigned_serial_numbers),
            customer.id,
            assigned_serial_numbers,
        )

        if invalid_serial_numbers:
            action_log.warning(
                "Assign device partial: user=%s customer=%s invalid=%s",
                user.id, customer.id, sorted(invalid_serial_numbers)
            )

        message = f"{len(assigned_serial_numbers)} device(s) assigned to customer successfully"
        if invalid_serial_numbers:
            message += f". {len(invalid_serial_numbers)} serial number(s) could not be assigned"

        return success_response(
            message=message,
            data={
                "customer_id": customer.id,
                "assigned_serial_numbers": assigned_serial_numbers,
                "invalid_serial_numbers": sorted(invalid_serial_numbers),
                "remaining_device_count": remaning_device_count - len(assigned_serial_numbers),
            },
        )
