import logging

from rest_framework import serializers

from django.db import transaction

from apps.core.models.device import Devices



class RegisterDeviceSerializer(serializers.ModelSerializer):

    class Meta:

        model = Devices
        fields = [
            'id',
            'serial_number',
            'device_type',
        ]
        read_only_fields = ['id']

    def validate_serial_number(self, value):
        value = value.strip()

        if Devices.objects.filter(serial_number=value).exists():
            raise serializers.ValidationError(
                "Device with this serial number already exists"
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user

        return Devices.objects.create(
            **validated_data,
            created_by=user
        )
