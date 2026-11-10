import logging

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.models.audit import AuditLog
from apps.core.utlis.audit import record_audit
from apps.core.utlis.responses import success_response

from ...serializers.auth import ProductionLoginSerializer


log_auth = logging.getLogger('aquacommunica.authlog')


class ProductionLoginView(APIView):
    """Login for the production APK (production role only)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ProductionLoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        user = data["user"]

        log_auth.info(
            "Production apk login successful | user_id=%s | email=%s",
            user.id, user.email,
        )

        record_audit(
            request,
            AuditLog.Action.LOGIN,
            user=user,
            instance=user,
            description=f"Production user {user.email} logged in (apk)",
        )

        return success_response(
            "Login successful",
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "is_verified": user.is_verified,
                },
                "tokens": {
                    "refresh": data["refresh"],
                    "access": data["access"],
                },
            },
        )
