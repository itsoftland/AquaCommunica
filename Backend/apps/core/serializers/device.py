from rest_framework import serializers

from ..models.device import Devices


class DeviceListSerializer(serializers.ModelSerializer):

    device_type_display = serializers.CharField(
        source='get_device_type_display',
        read_only=True
    )

    allocation_status_display = serializers.CharField(
        source='get_allocation_status_display',
        read_only=True
    )

    user_profile_name = serializers.CharField(
        source='user_profile.first_name',
        read_only=True,
        default=None
    )

    dealer_profile_name = serializers.CharField(
        source='dealer_profile.first_name',
        read_only=True,
        default=None
    )

    created_by_email = serializers.EmailField(
        source='created_by.email',
        read_only=True,
        default=None
    )

    class Meta:
        model = Devices
        fields = [
            'id',
            'serial_number',
            'device_type',
            'device_type_display',
            'allocation_status',
            'allocation_status_display',
            'is_active',
            'user_profile',
            'user_profile_name',
            'dealer_profile',
            'dealer_profile_name',
            'created_by_email',
            'created_at',
            'updated_at',
        ]
