import logging

from rest_framework import serializers

from ..models.tank import (
    Tank,
    TankDevice,
    TankDeviceRequirement,
    TankRoute
)
from ..models.customuser import CustomUser
from ..models.device import DeviceType, Devices


action_log = logging.getLogger('aquacommunica.action.log')

# Topology limits (FR#1 / FR#2 specs)
MAX_INBOUND_SLOTS         = 8   # transmitters/L1 repeaters per receiving repeater
MAX_REPEATER_LEVELS       = 2   # L1, then L2
MAX_REPEATERS_PER_SITE    = 9   # 8 L1 + 1 L2
MAX_TRANSMITTERS_PER_SITE = 64  # 8 L1 x 8 transmitters


def get_owner_profile(user):
    """Profile that owns the tanks: the user's own (admin) or their admin's (parent)."""
    if user.role == CustomUser.Role.USER_ADMIN:
        return user.user_profile
    if user.user_admin_id:
        return user.user_admin.user_profile
    return None


class createTankSerislizer(serializers.ModelSerializer):

    class Meta:

        model = Tank
        fields = [
            'name',
            'transmitter',
            'capacity_litres',
            'low_level_thresholds',
            'high_level_thresholds',
            'location',
        ]
        extra_kwargs = {
            'transmitter': {'required': True},
            'low_level_thresholds': {'required': True},
            'high_level_thresholds': {'required': True},
        }

    def _profile(self):
        profile = get_owner_profile(self.context['request'].user)

        if profile is None:
            action_log.warning(
                "Tank serializer: no profile | user_id=%s",
                self.context['request'].user.id,
            )
            raise serializers.ValidationError("No profile found for this user")
        
        return profile

    def validate_name(self, value):

        if Tank.objects.filter(user_profile=self._profile(), name=value).exists():
            action_log.warning("Tank create rejected: duplicate name | name=%s", value)
            raise serializers.ValidationError("You already have a tank with this name")
        
        return value

    def validate_transmitter(self, value):

        if value is None:
            return value
        
        if value.user_profile_id != self._profile().id:
            action_log.warning(
                "Tank create rejected: transmitter not owned | device_id=%s", value.pk
            )
            raise serializers.ValidationError("Entered device is not in your devices")
        
        if value.device_type != DeviceType.TRANSMITTER:
            action_log.warning(
                "Tank create rejected: not a transmitter | device_id=%s", value.pk
            )
            raise serializers.ValidationError("Device is not a transmitter")
        
        # if not value.is_active:
        #     raise serializers.ValidationError("Device is not active")
        
        if value.tank.filter(is_active=True).exists():
            action_log.warning(
                "Tank create rejected: transmitter already assigned | device_id=%s",
                value.pk,
            )
            raise serializers.ValidationError("Device is already assigned to a tank")
        
        return value

    def validate(self, attrs):

        if attrs['low_level_thresholds'] >= attrs['high_level_thresholds']:
            action_log.warning(
                "Tank create rejected: low threshold %s >= high threshold %s",
                attrs['low_level_thresholds'], attrs['high_level_thresholds'],
            )
            raise serializers.ValidationError(
                {"low_level_thresholds": "Must be less than high level threshold"}
            )
        
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user

        return Tank.objects.create(
            **validated_data,
            user_profile=self._profile(),
            created_by=user,
        )



class TankSerializer(serializers.ModelSerializer):

    class Meta:

        model = Tank
        fields = [
            'id',
            'name',
            'capacity_litres',
            'low_level_thresholds',
            'high_level_thresholds',
            'current_level_precent',
            'status',
            'last_reading_at',
            'location',
            'is_active',
            'is_configured',
            'created_at'
        ]
        read_only_fields = fields

    is_configured = serializers.SerializerMethodField()

    def get_is_configured(self, obj):
        return obj.tank_devices.exists()


class TankDeviceConfigSerializer(serializers.Serializer):
    # {"transmitter": 1, "repeater": 2, "gateway": 1, "receiver": 1, "pump_controller": 1}
    requirements = serializers.DictField(child=serializers.IntegerField(min_value=1))

    # {"transmitter": [5], "repeater": [6, 7], "gateway": [8], "receiver": [9], "pump_controller": [10]}
    devices  = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()))
    uplink   = serializers.ListField(child=serializers.IntegerField(), min_length=2)  # [5, 6, 7, 8]
    downlink = serializers.ListField(child=serializers.IntegerField(), min_length=2)  # [9, 10]

    def validate(self, attrs):
        tank = self.context["tank"]
        valid_types = set(DeviceType.values)

        # 1. counts must match the requirements
        for dtype, count in attrs["requirements"].items():
            if dtype not in valid_types:
                raise serializers.ValidationError(f"Unknown device type: {dtype}")
            if len(attrs["devices"].get(dtype, [])) != count:
                raise serializers.ValidationError(f"{dtype}: expected {count} device(s).")

        # 2. every device must exist, be of the right type, and belong to the tank owner
        all_ids = [i for ids in attrs["devices"].values() for i in ids]
        found = {
            d.id: d for d in Devices.objects.filter(id__in=all_ids, user_profile=tank.user_profile)
        }
        for dtype, ids in attrs["devices"].items():
            for i in ids:
                if i not in found or found[i].device_type != dtype:
                    raise serializers.ValidationError(f"Device {i} is not a valid {dtype} for this user.")

        # 3. check the chain shape
        def type_of(i): return found[i].device_type
        up, down = attrs["uplink"], attrs["downlink"]
        if type_of(up[0]) != DeviceType.TRANSMITTER or type_of(up[-1]) != DeviceType.GATEWAY:
            raise serializers.ValidationError("Uplink must start with a transmitter and end with a gateway.")
        if any(type_of(i) != DeviceType.REPEATER for i in up[1:-1]):
            raise serializers.ValidationError("Only repeaters are allowed between transmitter and gateway.")
        if tank.transmitter_id is not None and up[0] != tank.transmitter_id:
            raise serializers.ValidationError(
                {"uplink": "The uplink transmitter must match the tank's saved transmitter."}
            )
        if type_of(down[0]) != DeviceType.RECEIVER or type_of(down[-1]) != DeviceType.PUMP_CONTROLLER:
            raise serializers.ValidationError("Downlink must start with a receiver and end with a pump controller.")

        # 4. topology limits
        self._check_limits(attrs, type_of)

        attrs["_devices_by_id"] = found
        return attrs

    @staticmethod
    def _check_limits(attrs, type_of):
        up, down = attrs["uplink"], attrs["downlink"]
        counts = {t: len(ids) for t, ids in attrs["devices"].items()}

        # chains must not reuse a device (each device sends to exactly 1 next hop)
        for name, chain in (("Uplink", up), ("Downlink", down)):
            if len(set(chain)) != len(chain):
                raise serializers.ValidationError(f"{name} cannot contain the same device twice.")

        # devices in a chain must be part of the declared device list
        declared = {i for ids in attrs["devices"].values() for i in ids}
        if not set(up + down) <= declared:
            raise serializers.ValidationError("Uplink/downlink contain devices not listed in 'devices'.")

        # site-wide caps
        if counts.get(DeviceType.TRANSMITTER, 0) > MAX_TRANSMITTERS_PER_SITE:
            raise serializers.ValidationError(
                f"A site supports at most {MAX_TRANSMITTERS_PER_SITE} transmitters."
            )
        if counts.get(DeviceType.REPEATER, 0) > MAX_REPEATERS_PER_SITE:
            raise serializers.ValidationError(
                f"A site supports at most {MAX_REPEATERS_PER_SITE} repeaters."
            )
        if counts.get(DeviceType.GATEWAY, 0) > 1:
            raise serializers.ValidationError("Only 1 gateway is allowed per tank.")

        # repeater levels (L1 -> L2) in the uplink chain
        if len(up) - 2 > MAX_REPEATER_LEVELS:
            raise serializers.ValidationError(
                f"At most {MAX_REPEATER_LEVELS} repeater levels (L1, then L2) are allowed."
            )

        # inbound slots: no device may receive from more than 8 sources
        inbound = {}
        for chain in (up, down):
            for dst in chain[1:]:
                inbound[dst] = inbound.get(dst, 0) + 1
        # transmitters/L1 repeaters outside the chain still feed the first repeater/gateway
        extra_tx = counts.get(DeviceType.TRANSMITTER, 0) - 1
        first_hop = up[1]
        total_in = inbound.get(first_hop, 0) + max(extra_tx, 0)
        if total_in > MAX_INBOUND_SLOTS:
            raise serializers.ValidationError(
                f"A device accepts at most {MAX_INBOUND_SLOTS} inbound links; the 9th is refused."
            )

        # receiver -> pump controller is a single wired link
        if len(down) != 2:
            raise serializers.ValidationError("Downlink must be exactly receiver -> pump controller.")