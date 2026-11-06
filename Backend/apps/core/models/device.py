from django.db import models
from django.core.exceptions import ValidationError

from .profiles import UserProfile, DealerProfile
from .customuser import CustomUser


class DeviceType(models.TextChoices):

    REPEATER    = 'repeater', 'Repeater'
    TRANSMITTER = 'transmitter', 'Transmitter'
    RECEIVER    = 'receiver', 'Receiver'
    GATEWAY     = 'gateway', 'Gateway'


class AllocationStatus(models.TextChoices):

    STOCK    = 'stock', 'Stock'
    DEALER   = 'assigned_to_dealer', 'Assigned to Dealer'
    CUSTOMER = 'assigned_to_customer', 'Assigned to Customer'



class Devices(models.Model):

    serial_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True
    )

    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.TRANSMITTER,
        db_index=True
    )

    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices'
    )

    dealer_profile = models.ForeignKey(
        DealerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices'
    )

    allocation_status = models.CharField(
        max_length=20,
        choices=AllocationStatus.choices,
        default=AllocationStatus.STOCK,
        db_index=True
    )

    is_active = models.BooleanField(
        default=False
    )

    deactivated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices_deactivated"
    )

    deactivated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices_created'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )


    class Meta:
        db_table = 'devices'
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        ordering = ['-created_at']

        indexes = [
            models.Index(
                fields=['device_type', 'allocation_status'],
                name='device_type_alloc_idx'
            ),
            models.Index(
                fields=['user_profile', 'is_active'],
                name='device_user_active_idx'
            ),
            models.Index(
                fields=['dealer_profile', 'is_active'],
                name='device_dealer_active_idx'
            ),
            models.Index(
                fields=['allocation_status', 'is_active'],
                name='device_alloc_active_idx'
            ),
        ]


    def clean(self):
        super().clean()

        allocation_status = self.allocation_status

        if allocation_status not in [
            AllocationStatus.CUSTOMER,
            AllocationStatus.DEALER
        ]:
            return

        if allocation_status == AllocationStatus.DEALER:
            profile = self.dealer_profile

        if allocation_status == AllocationStatus.CUSTOMER:
            profile = self.user_profile

        if not profile:
            raise ValidationError(
                "Please select a valid profile for device allocation."
            )

        total_device_count = profile.total_device_count

        total_device_assigned = profile.devices.exclude(pk=self.pk).count()

        if total_device_assigned >= total_device_count:
            raise ValidationError(
                "Total device licence limit reached. Cannot assign another device."
            )
            

    def __str__(self):
        return f"{self.serial_number} - {self.device_type}"


