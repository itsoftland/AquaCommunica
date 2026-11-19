import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from ...models.customuser import CustomUser
from ...models.tank import Tank, TankStatus
from ...serializers.tank import (
    createTankSerislizer,
    TankSerializer,
    get_owner_profile
)
from ...models.audit import AuditLog
from ...utlis.audit import record_audit
from ...utlis.responses import error_response, success_response
from ...services.tank import get_tank


action_log = logging.getLogger('aquacommunica.action.log')


class AddTankView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    PARENT_USER = CustomUser.Role.PARENT_USER
    USER_ADMIN  = CustomUser.Role.USER_ADMIN

    def post(self, request):

        user = request.user

        if user.role not in [
            self.PARENT_USER,
            self.USER_ADMIN,
        ]:
            action_log.warning(
                "Add tank denied | user_id=%s role=%s", user.id, user.role
            )
            return error_response(
                message="you don't have the permission to add tank",
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = createTankSerislizer(
            data=request.data,
            context={
                "request": request
            }
        )

        if not serializer.is_valid():

            action_log.warning(
                "Add tank invalid data | user_id=%s errors=%s",
                user.id, serializer.errors,
            )
            return error_response(
                message="Invalid data",
                data=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        tank = serializer.save()

        action_log.info(
            "Tank created | user_id=%s tank_id=%s name=%s",
            user.id, tank.id, tank.name,
        )
        record_audit(
            request,
            AuditLog.Action.CREATE,
            user=user,
            instance=tank,
            description=f"Tank {tank.name} created",
            new_values={"id": tank.id, "name": tank.name},
        )

        return success_response(
            message="Tank added successfully.",
            data={
                "id": tank.id, 
                "name": tank.name
            }, 
            status=status.HTTP_201_CREATED,
        )


class TankSummaryView(APIView):
    """Quick tank analysis for user_admin, parent and child users."""

    permission_classes = [IsAuthenticated]

    ALLOWED = [
        CustomUser.Role.USER_ADMIN,
        CustomUser.Role.PARENT_USER,
        CustomUser.Role.CHILD_USER,
    ]

    def get(self, request):

        user = request.user

        if user.role not in self.ALLOWED:
            action_log.warning(
                "Tank summary denied | user_id=%s role=%s", user.id, user.role
            )
            return error_response(
                message="you don't have the permission to view tanks",
                status=status.HTTP_403_FORBIDDEN
            )

        profile = get_owner_profile(user)
        tanks = Tank.objects.filter(user_profile=profile, is_active=True) if profile else Tank.objects.none()

        counts = {s.value: 0 for s in TankStatus}
        for row in tanks.values_list("status", flat=True):
            counts[row] = counts.get(row, 0) + 1

        total_capacity = sum(t.capacity_litres for t in tanks)
        total_litres = sum(t.current_litres for t in tanks)

        items = [
            {
                "id": t.id,
                "name": t.name,
                "location": t.location,
                "status": t.status,
                "level_percent": float(t.current_level_precent),
                "current_litres": float(t.current_litres),
                "capacity_litres": t.capacity_litres,
                "last_reading_at": t.last_reading_at,
            }
            for t in tanks.order_by("id")
        ]

        action_log.info(
            "Tank summary fetched | user_id=%s tanks=%s", user.id, len(items)
        )

        return success_response(
            message="Tank summary fetched successfully.",
            data={
                "total": len(items),
                "status_counts": counts,
                "total_capacity_litres": total_capacity,
                "total_current_litres": float(total_litres),
                "average_level_percent": round(
                    sum(i["level_percent"] for i in items) / len(items), 1
                ) if items else 0,
                "tanks": items,
            },
        )


class TankDetailsView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    ALLOWED = [
        CustomUser.Role.USER_ADMIN,
        CustomUser.Role.PARENT_USER,
        CustomUser.Role.CHILD_USER,
    ]

    def get(self, request, pk):

        user = request.user
        
        if user.role not in self.ALLOWED:
            action_log.warning(
                "Tank Details denied | user_id=%s role=%s", user.id, user.role
            )
            return error_response(
                message="you don't have the permission to view tanks",
                status=status.HTTP_403_FORBIDDEN
            )

        tank = get_tank(pk=pk)

        profile = get_owner_profile(user)
        if profile is None or tank.user_profile_id != profile.id:
            action_log.warning(
                "Tank Details denied: not owner | user_id=%s tank_id=%s", user.id, pk
            )
            return error_response(
                message="Tank not found",
                status=status.HTTP_404_NOT_FOUND
            )

        return success_response(
            message="Tank details fetched successfully",
            data=TankSerializer(tank).data,
        )
