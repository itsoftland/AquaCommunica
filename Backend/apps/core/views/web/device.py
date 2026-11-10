import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from ...services.devices import get_all_devices
from ...serializers.device import DeviceListSerializer
from ...utlis.responses import success_response
from ...pagination import CustomPagination


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
