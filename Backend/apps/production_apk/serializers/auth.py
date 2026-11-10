import logging

from django.contrib.auth import authenticate

from rest_framework.exceptions import PermissionDenied

from apps.core.models.customuser import CustomUser
from apps.core.serializers.auth import LoginSerializer


log_auth = logging.getLogger('aquacommunica.authlog')


class ProductionLoginSerializer(LoginSerializer):
    """Login serializer that only lets users with the production role in."""

    def validate(self, attrs):
        # Role is checked only after the credentials are known to be valid
        # and before a session is started, so a rejected user never
        # logs out another device.
        user = authenticate(
            request=self.context.get("request"),
            email=attrs.get("email"),
            password=attrs.get("password"),
        )

        if user and user.role != CustomUser.Role.PRODUCTION:
            log_auth.info(
                "production apk login denied, role=%s | email=%s",
                user.role, user.email,
            )
            raise PermissionDenied(
                "Only production users can log in to this app."
            )

        return super().validate(attrs)