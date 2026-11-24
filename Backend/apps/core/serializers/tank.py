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
MAX_L1_REPEATERS          = 8   # level 1 repeaters per site
MAX_L2_REPEATERS          = 1   # level 2 repeater per site (optional)
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
        
        if Tank.objects.filter(transmitter=value).exists():
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
        # transmitter -> L1 -> L1 -> ... -> [L2] -> gateway (L1 repeaters are daisy-chained)
        middle = [type_of(i) for i in up[1:-1]]
        l1_count = len([t for t in middle if t == DeviceType.REPEATER_L1])
        expected = [DeviceType.REPEATER_L1] * l1_count + (
            [DeviceType.REPEATER_L2] if DeviceType.REPEATER_L2 in middle else []
        )
        if middle != expected:
            raise serializers.ValidationError(
                "Uplink must be transmitter -> L1 repeater(s) -> [L2 repeater] -> gateway."
            )
        if attrs["devices"].get(DeviceType.REPEATER_L2) and not l1_count:
            raise serializers.ValidationError("A level 2 repeater requires at least one level 1 repeater.")
        for rtype in (DeviceType.REPEATER_L1, DeviceType.REPEATER_L2):
            if set(attrs["devices"].get(rtype, [])) != {i for i in up[1:-1] if type_of(i) == rtype}:
                raise serializers.ValidationError("Every selected repeater must be part of the uplink chain.")
        if tank.transmitter_id is not None and up[0] != tank.transmitter_id:
            raise serializers.ValidationError(
                {"uplink": "The uplink transmitter must match the tank's saved transmitter."}
            )
        if Tank.objects.filter(transmitter_id=up[0]).exclude(pk=tank.pk).exists():
            raise serializers.ValidationError(
                {"uplink": "This transmitter is already assigned to another tank."}
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
        if counts.get(DeviceType.REPEATER_L1, 0) > MAX_L1_REPEATERS:
            raise serializers.ValidationError(
                f"A site supports at most {MAX_L1_REPEATERS} level 1 repeaters."
            )
        if counts.get(DeviceType.REPEATER_L2, 0) > MAX_L2_REPEATERS:
            raise serializers.ValidationError(
                f"A site supports at most {MAX_L2_REPEATERS} level 2 repeater."
            )
        if counts.get(DeviceType.GATEWAY, 0) > 1:
            raise serializers.ValidationError("Only 1 gateway is allowed per tank.")

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