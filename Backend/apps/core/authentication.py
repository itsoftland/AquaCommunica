from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

SESSION_EXPIRED_MESSAGE = "Session expired. Logged in on another device."
LOGGED_OUT_MESSAGE = "You are logged out. Please log in again."


def session_error_message(user, token):
    """Pick the message matching why the token's session is invalid."""
    if user is None or not user.session_id:
        return LOGGED_OUT_MESSAGE
    if token.get("session_id") != user.session_id:
        return SESSION_EXPIRED_MESSAGE
    return None


class SingleSessionJWTAuthentication(JWTAuthentication):
    """JWT auth that rejects tokens whose session_id is not the user's current one."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        message = session_error_message(user, validated_token)
        if message:
            raise AuthenticationFailed(message, code="session_expired")

        return user
