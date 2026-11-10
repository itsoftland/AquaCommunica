import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.core.utlis.responses import error_response, success_response
from apps.core.models.audit import AuditLog
from apps.core.utlis.audit import record_audit
from ...serializers.device import RegisterDeviceSerializer

log_device = logging.getLogger('aquacommunica.devicelog')



class RegisterDeviceView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):

        user = request.user

        if not user.is_production:

            log_device.info(
                "Device register denied (not production user) | user_id=%s",
                user.pk
            )

            return error_response(
                message="you don't have permission to add device",
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = RegisterDeviceSerializer(
            data=request.data,
            context={
                'request': request
            }
        )

        if serializer.is_valid():
            device = serializer.save()

            log_device.info(
                "Device registered | user_id=%s device_id=%s serial=%s",
                user.pk, device.pk, device.serial_number
            )

            record_audit(
                request,
                AuditLog.Action.CREATE,
                user=user,
                instance=device,
                description=f"Device {device.serial_number} registered",
                new_values=serializer.data,
            )

            return success_response(
                message="Device registered successfully.",
                data=serializer.data,
                status=status.HTTP_201_CREATED
            )

        log_device.warning(
            "Device registration failed validation | user_id=%s errors=%s",
            user.pk, serializer.errors
        )

        return error_response(
            message="Device registration failed.",
            data=serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
        