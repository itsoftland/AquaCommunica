import logging

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from ...utlis.responses import success_response
from ...utlis.audit import record_audit
from apps.core.models.audit import AuditLog
from apps.core.serializers.auth import (
    LoginSerializer, 
    UserRegisterSerializer, 
    LogoutSerializer
)
from ...models.customuser import CustomUser
from ...models.profiles import UserProfile, DealerProfile

log_auth = logging.getLogger('aquacommunica.authlog')


class LoginView(APIView):
    """Authenticate a user and return their profile details with JWT tokens."""

    permission_classes = [AllowAny, ]

    def post(self, request):

        log_auth.info(
            "Initializing login request | email=%s",
            request.data.get("email")
        )

        serilalizer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )

        serilalizer.is_valid(raise_exception=True)

        data = serilalizer.validated_data

        user = data["user"]

        user_details = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_verified": user.is_verified,
        }

        log_auth.info(
            "Login successful | user_id=%s | email=%s | role=%s",
            user.id,
            user.email,
            user.role,
        )

        record_audit(
            request,
            AuditLog.Action.LOGIN,
            user=user,
            instance=user,
            description=f"User {user.email} logged in",
        )

        return success_response(
            "Login successful",
            {
                "user": user_details,
                "tokens": {
                    "refresh": data["refresh"],
                    "access": data["access"],
                },
            },
        )



class ProfileView(APIView):
    """Return the authenticated user's profile details."""

    permission_classes = [IsAuthenticated,]

    def get(self, request):

        user = request.user

        user_details = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_verified": user.is_verified,
        }

        return success_response(
            "You are authenticated",
            {"user": user_details},
        )



class UserRegisterView(APIView):
    """Create a user account and return the new user's details."""

    permission_classes = [IsAuthenticated, ]

    def post(self, request):

        log_auth.info(
            "Initializing user registration request | email=%s",
            request.data.get("email")
        )

        data = request.data

        serializer = UserRegisterSerializer(
            data=data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        log_auth.info(
            "User registration succesfully completed | user id = %s | email=%s | role=%s |",
            user.id,
            user.email,
            user.role,
        )

        record_audit(
            request,
            AuditLog.Action.CREATE,
            user=request.user,
            instance=user,
            description=f"User {user.email} created",
            new_values={"email": user.email, "role": user.role},
        )

        return success_response(
            "User created successfully.",
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "is_verified": user.is_verified,
                    "created_by": user.created_by.email,
                }
            },
            status=status.HTTP_201_CREATED,
        )



class LogoutView(APIView):
    """Log out the authenticated user by invalidating their refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_auth.info(
            "Logout successful."
        )

        record_audit(
            request,
            AuditLog.Action.LOGOUT,
            user=request.user,
            instance=request.user,
            description=f"User {request.user.email} logged out",
        )
        return success_response("Logout successful.")


class DashboardView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        SUPER_ADMIN = CustomUser.Role.SUPERADMIN
        USER_ADMIN  = CustomUser.Role.USER_ADMIN
        PRODUCTION  = CustomUser.Role.PRODUCTION
        EXECUTIVE   = CustomUser.Role.EXECUTIVE
        DEALER      = CustomUser.Role.DEALER
        PARENT      = CustomUser.Role.PARENT_USER
        CHILD       = CustomUser.Role.CHILD_USER

        APPROVED   = UserProfile.AuthStatus.APPROVED
        EXPIRED    = UserProfile.AuthStatus.EXPIRED
        PENDING    = UserProfile.AuthStatus.PENDING
        VALIDATING = UserProfile.AuthStatus.VALIDATING
        

        if user.role == SUPER_ADMIN:

            users = CustomUser.objects.exclude(
                role=SUPER_ADMIN
            )

            total_users = users.count()
            total_active_users = users.filter(
                is_active=True
            ).count()
            total_inactive_users = users.filter(
                is_active=False
            ).count()


            customers = UserProfile.objects

            total_customers = customers.count()
            total_validated_customers = customers.filter(
                authentication_status=APPROVED
            ).count()
            total_invalidated_customers = customers.filter(
                authentication_status__in=[
                    PENDING,
                    VALIDATING,
                ]
            ).count()
            total_expired_customers = customers.filter(
                authentication_status=EXPIRED
            ).count()


            dealers = DealerProfile.objects

            total_dealers = dealers.count()
            total_validated_dealers = dealers.filter(
                authentication_status=APPROVED
            ).count()
            total_invalidated_dealers = dealers.filter(
                authentication_status__in=[
                    PENDING,
                    VALIDATING,
                ]
            ).count()
            total_expired_dealers = dealers.filter(
                authentication_status=EXPIRED
            ).count()


            return success_response(
                message="Dashboard stats fetched successfully",
                data={
                    "users": {
                        "total": total_users,
                        "active": total_active_users,
                        "inactive": total_inactive_users,
                    },
                    "customers": {
                        "total": total_customers,
                        "validated": total_validated_customers,
                        "invalidated": total_invalidated_customers,
                        "expired": total_expired_customers,
                    },
                    "dealers": {
                        "total": total_dealers,
                        "validated": total_validated_dealers,
                        "invalidated": total_invalidated_dealers,
                        "expired": total_expired_dealers,
                    },
                },
            )

        if user.role in [
            DEALER,
            EXECUTIVE
        ]:

            customers = UserProfile.objects

            total_customers = customers.filter(
                created_by=user
            ).count()
            total_validated_customers = customers.filter(
                authentication_status=APPROVED,
                created_by=user
            ).count()
            total_invalidated_customers = customers.filter(
                authentication_status__in=[
                    PENDING,
                    VALIDATING,
                ],
                created_by=user
            ).count()
            total_expired_customers = customers.filter(
                authentication_status=EXPIRED,
                created_by=user
            ).count()


            return success_response(
                message="Dashboard stats fetched successfully",
                data={
                    "customers": {
                        "total": total_customers,
                        "validated": total_validated_customers,
                        "invalidated": total_invalidated_customers,
                        "expired": total_expired_customers,
                    },
                },
            )

        if user.role == USER_ADMIN:

            users = CustomUser.objects

            total_users = users.filter(
                role__in=[
                    PARENT,
                    CHILD
                ],
                created_by=user
            ).count()
            total_active_users = users.filter(
                role__in=[
                    PARENT,
                    CHILD
                ],
                created_by=user
            ).count()
            total_parent_user = users.filter(
                role=PARENT,
                created_by=user
            ).count()
            total_child_user = total_users - total_parent_user

            return success_response(
                message="Dashboard stats fetched successfully",
                data={
                    "users": {
                        "total": total_users,
                        "active": total_active_users,
                        "inactive": total_users - total_active_users,
                        "parents": total_parent_user,
                        "children": total_child_user,
                    },
                },
            )
            
        if user.role == PRODUCTION:

            return success_response(
                message="Dashboard stats fetched successfully",
                data={},
            )

        if user.role in [
            PARENT,
            CHILD
        ]:
            return success_response(
                message="Dashboard stats fetched successfully",
                data={},
            )