import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from django.db import transaction

from ...models.customuser import CustomUser
from ...models.tank import (
    Tank, 
    TankStatus,
    TankDevice,
    TankDeviceRequirement,
    TankRoute
)
from ...serializers.tank import (
    createTankSerislizer,
    TankSerializer,
    get_owner_profile,
    TankDeviceConfigSerializer
)
from ...models.device import DeviceType
from ...models.audit import AuditLog
from ...utlis.audit import record_audit
from ...utlis.responses import error_response, success_response
from ...services.tank import get_tank


action_log = logging.getLogger('aquacommunica.action.log')


USER_ADMIN  = CustomUser.Role.USER_ADMIN
PARENT_USER = CustomUser.Role.PARENT_USER
CHILD_USER  = CustomUser.Role.CHILD_USER



class AddTankView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):

        user = request.user

        if user.role not in [
            PARENT_USER,
            USER_ADMIN,
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
        USER_ADMIN,
        PARENT_USER,
        CHILD_USER,
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
        tanks = Tank.objects.filter(user_profile=profile) if profile else Tank.objects.none()

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
                "transmitter_id": t.transmitter_id,
                "status": t.status,
                "is_active": t.is_active,
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
        USER_ADMIN,
        PARENT_USER,
        CHILD_USER,
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


class TankActiveandDeactive(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, pk):

        user = request.user

        if user.role not in [
            USER_ADMIN,
            PARENT_USER,
        ]:
            action_log.warning(
                "Tank activate/deactivate denied | user_id=%s role=%s tank_id=%s",
                user.id, user.role, pk,
            )
            return error_response(
                message="you don't have permission to activate or deactivate tank",
                status=status.HTTP_403_FORBIDDEN
            )

        tank = get_tank(pk=pk)
        
        profile = get_owner_profile(user)
        if profile is None or tank.user_profile_id != profile.id:
            action_log.warning(
                "Tank activate/deactivate denied: not owner | user_id=%s tank_id=%s", user.id, pk
            )
            return error_response(
                message="Tank not found",
                status=status.HTTP_404_NOT_FOUND
            )

        old_active = tank.is_active
        tank.is_active = not old_active

        if tank.is_active:
            level = tank.current_level_precent

            if level is None:
                tank.status = TankStatus.OFFLINE
            elif level >= tank.high_level_thresholds:
                tank.status = TankStatus.OVERFLOW
            elif level > tank.low_level_thresholds:
                tank.status = TankStatus.NORMAL
            elif level > tank.low_level_thresholds / 2:
                tank.status = TankStatus.LOW
            else:
                tank.status = TankStatus.CRITICAL

        else:
            tank.status = TankStatus.OFFLINE
            
        tank.save(update_fields=[
            'is_active',
            'status'
        ])

        state = "activated" if tank.is_active else "deactivated"
        action_log.info(
            "Tank %s | user_id=%s tank_id=%s", state, user.id, pk
        )
        record_audit(
            request,
            AuditLog.Action.UPDATE,
            user=user,
            instance=tank,
            description=f"Tank {tank.name} {state}",
            old_values={"is_active": old_active},
            new_values={"is_active": tank.is_active},
        )

        return success_response(
            message=f"Tank {state} successfully",
            data={"id": tank.id, "is_active": tank.is_active},
        )


class TankDeviceConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        if user.role not in [USER_ADMIN, PARENT_USER, CHILD_USER]:
            return error_response(
                message="you don't have the permission to view tank devices",
                status=status.HTTP_403_FORBIDDEN,
            )

        profile = get_owner_profile(user)
        try:
            tank = Tank.objects.get(pk=pk, user_profile=profile)
        except Tank.DoesNotExist:
            return error_response(message="Tank not found", status=status.HTTP_404_NOT_FOUND)

        links = list(tank.tank_devices.select_related("device"))
        requirements = {r.device_type: r.count for r in tank.requirements.all()}
        devices = {}
        for link in links:
            devices.setdefault(link.device.device_type, []).append(
                {"id": link.device_id, "serial_number": link.device.serial_number}
            )

        routes = list(tank.routes.all())  # ordered by direction, hop_order

        def chain(direction):
            hops = [r for r in routes if r.direction == direction]
            if not hops:
                return []
            return [hops[0].source_id] + [r.destination_id for r in hops]

        return success_response(
            message="Tank device configuration fetched successfully.",
            data={
                "is_configured": bool(links),
                "requirements": requirements,
                "devices": devices,
                "uplink": chain("uplink"),
                "downlink": chain("downlink"),
            },
        )

    def post(self, request, pk):
        user = request.user
        if user.role not in [PARENT_USER, USER_ADMIN]:
            return error_response(
                message="you don't have the permission to configure tank devices",
                status=status.HTTP_403_FORBIDDEN,
            )

        profile = get_owner_profile(user)
        try:
            tank = Tank.objects.get(pk=pk, user_profile=profile)
        except Tank.DoesNotExist:
            return error_response(message="Tank not found", status=status.HTTP_404_NOT_FOUND)

        serializer = TankDeviceConfigSerializer(data=request.data, context={"tank": tank})
        if not serializer.is_valid():
            return error_response(message="Invalid data", data=serializer.errors,
                                  status=status.HTTP_400_BAD_REQUEST)

        data  = serializer.validated_data
        found = data["_devices_by_id"]

        with transaction.atomic():
            # lock the tank so concurrent re-configs run one at a time
            Tank.objects.select_for_update().get(pk=tank.pk)

            # wipe and rebuild so re-configuring is idempotent
            tank.requirements.all().delete()
            tank.tank_devices.all().delete()
            tank.routes.all().delete()

            TankDeviceRequirement.objects.bulk_create([
                TankDeviceRequirement(tank=tank, device_type=t, count=c)
                for t, c in data["requirements"].items()
            ])
            TankDevice.objects.bulk_create([
                TankDevice(tank=tank, device=found[i])
                for ids in data["devices"].values() for i in ids
            ])

            routes = []
            for direction, chain in (("uplink", data["uplink"]), ("downlink", data["downlink"])):
                for n in range(len(chain) - 1):
                    routes.append(TankRoute(
                        tank=tank, direction=direction, hop_order=n,
                        source=found[chain[n]], destination=found[chain[n + 1]],
                    ))

            TankRoute.objects.bulk_create(routes)

            # keep the existing FK in sync
            tank.transmitter = found[data["uplink"][0]]
            tank.save(update_fields=["transmitter"])

        record_audit(request, AuditLog.Action.UPDATE, user=user, instance=tank,
                     description=f"Tank {tank.name} devices configured")
        return success_response(message="Tank devices configured.", status=status.HTTP_200_OK)