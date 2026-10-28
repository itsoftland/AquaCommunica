from django.db import models

from .customuser import CustomUser


class AuditLog(models.Model):

    # =========================================================
    # CHOICES
    # =========================================================

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        OTHER = "other", "Other"

    # =========================================================
    # WHO / WHAT
    # =========================================================

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        default=Action.OTHER,
        db_index=True,
    )

    # =========================================================
    # TARGET
    # =========================================================

    model_name = models.CharField(
        max_length=100,
        blank=True,
    )

    object_id = models.CharField(
        max_length=64,
        blank=True,
    )

    description = models.CharField(
        max_length=500,
        blank=True,
    )

    # =========================================================
    # CHANGE DETAILS
    # =========================================================

    old_values = models.JSONField(
        null=True,
        blank=True,
    )

    new_values = models.JSONField(
        null=True,
        blank=True,
    )

    # =========================================================
    # REQUEST INFORMATION
    # =========================================================

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.CharField(
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        db_table = "audit_log"

        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["model_name", "object_id"],
                name="audit_target_idx",
            ),
            models.Index(
                fields=["user", "action"],
                name="audit_user_action_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="audit_created_at_idx",
            ),
        ]

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return f"{self.action} {self.model_name}#{self.object_id} by {self.user_id}"
