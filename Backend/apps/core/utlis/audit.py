import logging

from apps.core.models.audit import AuditLog

log_audit = logging.getLogger('aquacommunica.authlog')


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_audit(request, action, user=None, instance=None, description="",
                 old_values=None, new_values=None):
    """Write an AuditLog row; never let a logging failure break the request."""
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=instance.__class__.__name__ if instance is not None else "",
            object_id=str(instance.pk) if instance is not None else "",
            description=description[:500],
            old_values=old_values,
            new_values=new_values,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
    except Exception:
        log_audit.exception("Failed to write audit log | action=%s", action)
