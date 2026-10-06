from django.db import models
from django.core.exceptions import ValidationError

from .customuser import CustomUser


class UserProfile(models.Model):

    # =========================================================
    # CHOICES
    # =========================================================

    class ClientType(models.TextChoices):
        DEALER = "dealer", "Dealer"
        DIRECT = "direct", "Direct"

    class AuthStatus(models.TextChoices):
        PENDING = "Pending", "Pending"
        VALIDATING = "Validating", "Validating"
        APPROVED = "Approved", "Approved"
        EXPIRED = "Expired", "Expired"
        BLOCKED = "Blocked", "Blocked"

    # =========================================================
    # USER / PROFILE IDENTIFICATION
    # =========================================================

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="user_profile",
        limit_choices_to={"role": "user_admin"},
    )

    profile_id = models.CharField(
        max_length=6,
        unique=True,
        blank=True,
    )

    # =========================================================
    # PERSONAL INFORMATION
    # =========================================================

    first_name = models.CharField(
        max_length=100,
        blank=True,
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
    )

    contact_email = models.EmailField(
        max_length=255,
        blank=True,
    )

    # =========================================================
    # ADDRESS INFORMATION
    # =========================================================

    address = models.TextField(
        blank=True,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
    )

    state = models.CharField(
        max_length=100,
        blank=True,
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
    )

    # =========================================================
    # BUSINESS INFORMATION
    # =========================================================

    gst_number = models.CharField(
        max_length=20,
        blank=True,
    )

    client_type = models.CharField(
        max_length=10,
        choices=ClientType.choices,
        default=ClientType.DIRECT,
        db_index=True,
    )

    dealer = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dealer_created_profiles",
        limit_choices_to={"role": "dealer"},
    )

    # =========================================================
    # AUTHENTICATION / ACCOUNT STATUS
    # =========================================================

    authentication_status = models.CharField(
        max_length=25,
        choices=AuthStatus.choices,
        default=AuthStatus.PENDING,
        db_index=True,
    )

    is_profile_active = models.BooleanField(
        default=False,
    )

    # =========================================================
    # VALIDITY
    # =========================================================

    validity_from_date = models.DateField(
        null=True,
        blank=True,
    )

    validity_to_date = models.DateField(
        null=True,
        blank=True,
    )

    # =========================================================
    # LICENSE / USAGE
    # =========================================================

    total_licence_unit = models.PositiveIntegerField(
        default=0,
    )

    total_user_count = models.PositiveIntegerField(
        default=0,
    )

    parent_user_count = models.PositiveIntegerField(
        default=0,
    )

    child_user_count = models.PositiveIntegerField(
        default=0,
    )

    total_device_count = models.PositiveIntegerField(
        default=0,
    )

    # =========================================================
    # AUDIT INFORMATION
    # =========================================================

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_profiles",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        db_table = "userprofile"

        verbose_name = "UserProfile"
        verbose_name_plural = "UserProfiles"

        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["client_type", "authentication_status"],
                name="profile_client_auth_idx",
            ),
            models.Index(
                fields=["dealer", "authentication_status"],
                name="profile_dealer_auth_idx",
            ),
            models.Index(
                fields=["validity_to_date"],
                name="profile_validity_idx",
            ),
        ]

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):
        super().clean()

        total_usage = (
            self.total_user_count +
            self.total_device_count
        )

        if total_usage > self.total_licence_unit:
            raise ValidationError(
                "Total users + total devices cannot be more "
                "than total licence units."
            )

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return f"{self.profile_id} - {self.user.email}"
