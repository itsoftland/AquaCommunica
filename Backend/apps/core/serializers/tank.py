from rest_framework import serializers

from django.db import transaction

from ..models.tank import Tank
from ..models.customuser import CustomUser
from ..models.device import DeviceType


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
            raise serializers.ValidationError("No profile found for this user")
        
        return profile

    def validate_name(self, value):

        if Tank.objects.filter(user_profile=self._profile(), name=value).exists():
            raise serializers.ValidationError("You already have a tank with this name")
        
        return value

    def validate_transmitter(self, value):

        if value is None:
            return value
        
        if value.user_profile_id != self._profile().id:
            raise serializers.ValidationError("Entered device is not in your devices")
        
        if value.device_type != DeviceType.TRANSMITTER:
            raise serializers.ValidationError("Device is not a transmitter")
        
        # if not value.is_active:
        #     raise serializers.ValidationError("Device is not active")
        
        if value.tank.filter(is_active=True).exists():
            raise serializers.ValidationError("Device is already assigned to a tank")
        
        return value

    def validate(self, attrs):

        if attrs['low_level_thresholds'] >= attrs['high_level_thresholds']:
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