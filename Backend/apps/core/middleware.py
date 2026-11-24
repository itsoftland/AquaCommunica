import logging

from django.http import JsonResponse
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError

from .models.customuser import CustomUser

log_auth = logging.getLogger('aquacommunica.authlog')

Role = CustomUser.Role


class LicenseValidityMiddleware:
    """Block API calls from user_admin, parent_user, child_user and dealer
    accounts whose license profile is missing, inactive or expired.

    - user_admin           -> own ``user_profile``
    - parent_user / child  -> their user admin's ``user_profile``
    - dealer               -> own ``dealer_profile``

    Other roles (superadmin, executive, production) are never checked. Requests
    without a valid bearer token are passed through so DRF can answer them.
    Login, token refresh and logout stay open so a blocked user can still sign
    out (login applies the same checks itself).
    """

    API_PREFIXES = ("/AQUACOMMUNICA/web/core/", "/AQUACOMMUNICA/apk-1/")
    EXEMPT_SUFFIXES = ("login/", "token/refresh/", "logout/")

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt = JWTAuthentication()

    def __call__(self, request):
        message = self.check(request)
        if message:
            return JsonResponse(
                {"success": False, "message": message, "data": None},
                status=403,
            )
        return self.get_response(request)

    def check(self, request):
        path = request.path
        if not path.startswith(self.API_PREFIXES) or path.endswith(self.EXEMPT_SUFFIXES):
            return None

        user = self.get_user(request)
        if user is None:
            return None

        if user.role == Role.DEALER:
            owner, attr, label = user, "dealer_profile", "dealer"
        elif user.role == Role.USER_ADMIN:
            owner, attr, label = user, "user_profile", "user admin"
        elif user.role in (Role.PARENT_USER, Role.CHILD_USER):
            owner, attr, label = user.user_admin, "user_profile", "user admin"
        else:
            return None

        profile = getattr(owner, attr, None) if owner else None
        message = self.profile_problem(profile)

        # users of a deactivated dealer are blocked as well
        dealer = getattr(owner, "dealer", None) if owner and user.role != Role.DEALER else None
        if message is None and dealer is not None and not dealer.is_active:
            message = "Your dealer account is deactivated. Contact admin."

        if message:
            log_auth.warning(
                "License check blocked request | user_id=%s role=%s path=%s reason=%s",
                user.id, user.role, path, message,
            )
        return message

    @staticmethod
    def profile_problem(profile):
        if profile is None:
            return "We can't find your license profile. Contact admin."
        if not profile.is_profile_active:
            return "Your profile is not active. Contact admin."
        if profile.validity_to_date is None or profile.validity_to_date < timezone.localdate():
            return "Your license is missing or has expired. Contact admin for renewal."
        return None

    def get_user(self, request):
        header = self.jwt.get_header(request)
        if header is None:
            return None
        raw = self.jwt.get_raw_token(header)
        if raw is None:
            return None
        try:
            token = self.jwt.get_validated_token(raw)
            return self.jwt.get_user(token)
        except (InvalidToken, TokenError, AuthenticationFailed):
            return None  # let DRF produce the proper 401
