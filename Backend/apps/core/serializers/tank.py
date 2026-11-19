import logging

from rest_framework import serializers

from ..models.tank import Tank
from ..models.customuser import CustomUser
from ..models.device import DeviceType


action_log = logging.getLogger('aquacommunica.action.log')


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
            'created_at'
        ]
        read_only_fields = fields