from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

from ..models.customuser import CustomUser
from ..models.profiles import UserProfile
from ..models.device import Devices, DeviceType


class TankStatus(models.TextChoices):

    NORMAL   = "normal", "Normal"
    LOW      = "low", "Low"
    CRITICAL = "critical", "Critical"
    OVERFLOW = "overflow", "Overflow"
    OFFLINE  = "offline", "Offline"

class Direction(models.TextChoices):
        UPLINK   = 'uplink', 'Uplink'      # transmitter -> repeater(s) -> gateway -> server
        DOWNLINK = 'downlink', 'Downlink'  # server -> receiver -> pump controller


class Tank(models.Model):

    name = models.CharField(
        max_length=100
    )

    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="tanks"
    )

    transmitter = models.OneToOneField(
        Devices,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tank",
        limit_choices_to={"device_type": DeviceType.TRANSMITTER}
    )

    capacity_litres = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total tank capacity in litres"
    )

    low_level_thresholds = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    high_level_thresholds = models.PositiveSmallIntegerField(
        default=90,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    current_level_precent = models.DecimalField(
        default=Decimal('0.00'),
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ]
    )

    status = models.CharField(
        max_length=20,
        choices=TankStatus.choices,
        default=TankStatus.OFFLINE,
        db_index=True
    )

    last_reading_at = models.DateTimeField(
        null=True,
        blank=True
    )

    location = models.CharField(
        max_length=255,
        blank=True
    )

    is_active = models.BooleanField(
        default=False
    )

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tanks_created'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:

        db_table = 'tanks'
        verbose_name = 'Tank'
        verbose_name_plural = 'Tanks'
        ordering = ['-created_at']


        constraints = [
            models.UniqueConstraint(
                fields=['user_profile', 'name'],
                name='unique_tank_name_per_user'
            ),
        ]

        indexes = [
            models.Index(
                fields=['user_profile', 'is_active'],
                name='tank_user_active_idx'
            ),
            models.Index(
                fields=['status', 'is_active'],
                name='tank_status_active_idx'
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.capacity_litres} L)"

    def clean(self):
        super().clean()
        if self.low_level_thresholds >= self.high_level_thresholds:
            raise ValidationError(
                "Low level threshold must be less than high level threshold."
            )
        if self.transmitter and self.transmitter.device_type != DeviceType.TRANSMITTER:
            raise ValidationError(
                {"transmitter": "Selected device must be a transmitter."}
            )

        if (
            self.transmitter
            and not self.user_profile.devices.filter(pk=self.transmitter.pk).exists()
        ):
            raise ValidationError(
                {"transmitter": "Selected transmitter is not assigned to this user."}
            )

    @property
    def current_litres(self):
        return (self.capacity_litres * self.current_level_precent / Decimal('100')).quantize(Decimal('0.01'))


class TankDeviceRequirement(models.Model):
    """Step 1: how many devices of each type this tank needs."""

    tank = models.ForeignKey(
        Tank,
        on_delete=models.CASCADE,
        related_name="requirements"
    )

    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.REPEATER_L1
    )

    count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        db_table = 'tank_device_requirements'
        constraints = [
            models.UniqueConstraint(
                fields=['tank', 'device_type'],
                name='unique_requirement_per_tank_type'
            ),
        ]    


class TankDevice(models.Model):
    """Step 2: which actual devices belong to this tank."""

    tank = models.ForeignKey(
        Tank,
        on_delete=models.CASCADE,
        related_name="tank_devices"
    ) 

    device = models.ForeignKey(
        Devices,
        on_delete=models.CASCADE,
        related_name="tank_links"
    )

    class Meta:
        db_table = 'tank_devices'
        constraints = [
            models.UniqueConstraint(
                fields=['tank', 'device'],
                name='unique_device_per_tank'
            ),
        ]


class TankRoute(models.Model):
    """Step 3: who sends to whom (one hop per row)."""

    tank = models.ForeignKey(
        Tank, 
        on_delete=models.CASCADE, 
        related_name="routes"
    )

    source = models.ForeignKey(
        Devices, 
        on_delete=models.CASCADE, 
        related_name="routes_out"
    )

    destination = models.ForeignKey(
        Devices, 
        on_delete=models.CASCADE, 
        related_name="routes_in"
    )

    direction = models.CharField(
        max_length=10, 
        choices=Direction.choices
    )

    hop_order = models.PositiveSmallIntegerField()

    class Meta:
        db_table = 'tank_routes'
        ordering = ['direction', 'hop_order']
        constraints = [
            models.UniqueConstraint(
                fields=['tank', 'direction', 'source'], 
                name='unique_hop_source'
            ),
        ]
