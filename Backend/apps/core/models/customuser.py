import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


from apps.core.managers import CustomUserManager


class CustomUser(AbstractUser):

    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", "Super Admin"
        EXECUTIVE = "executive", "Executive"
        DEALER = "dealer", "Dealer"
        PRODUCTION = "production", "Production"
        PARENT_USER = "parent_user", "Parent User"
        CHILD_USER = "child_user", "Child User"

    username = None

    email = models.EmailField(
        unique=True,
        max_length=255,
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CHILD_USER,
        db_index=True,
    )

    dealer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_users',
        limit_choices_to={"role": "dealer"},
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_users",
        limit_choices_to={"role": "parent_user"},
    )

    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_users",
    )

    # is_active = models.BooleanField(default=True)

    is_verified = models.BooleanField(default=False)

    # Identifies the single active login session; embedded in every JWT.
    session_id = models.CharField(max_length=64, null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)


    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    
    class Meta:
        db_table = "customuser"
        verbose_name = "CustomUser"
        verbose_name_plural = "CustomUsers"
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["role", "is_active"],
                name="user_role_active_idx"
            ),
            models.Index(
                fields=["dealer", "role"],
                name="user_dealer_role_idx"
            ),
            models.Index(
                fields=["-created_at"],
                name="user_date_joined_idx"
            ),
        ]

    def clean(self):
        super().clean()

        if self.dealer and self.dealer.role != self.Role.DEALER:
            raise ValidationError({
                "dealer": "Assigned user must be a dealer."
            })

        if self.parent and self.parent.role != self.Role.PARENT_USER:
            raise ValidationError({
                "parent": "Parent must have the parent_user role."
            })

        if self.parent and self.parent_id == self.pk:
            raise ValidationError({
                "parent": "A user cannot be their own parent."
            })

        if self.dealer and self.dealer_id == self.pk:
            raise ValidationError({
                "dealer": "A user cannot be their own dealer."
            })


    def start_new_session(self):
        self.session_id = uuid.uuid4().hex
        self.save(update_fields=["session_id"])
        return self.session_id

    def end_session(self):
        self.session_id = None
        self.save(update_fields=["session_id"])

    def __str__(self):
        return f"{self.email} ({self.role})"


    @property
    def is_superadmin(self):
        return self.role == self.Role.SUPERADMIN

    @property
    def is_parent_user(self):
        return self.role == self.Role.PARENT_USER

    @property
    def is_child_user(self):
        return self.role == self.Role.CHILD_USER

    @property
    def is_dealer(self):
        return self.role == self.Role.DEALER

