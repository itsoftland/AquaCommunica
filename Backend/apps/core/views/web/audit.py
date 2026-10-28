from django.core.paginator import Paginator
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ...models.audit import AuditLog
from ...permissions import IsSuperAdmin
from ...utlis.responses import success_response


class AuditLogListView(APIView):
    """List audit logs (newest first). Super admin only."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        logs = AuditLog.objects.select_related("user")

        action = request.query_params.get("action")
        if action:
            logs = logs.filter(action=action)

        try:
            page_size = min(max(int(request.query_params.get("page_size", 25)), 1), 100)
        except ValueError:
            page_size = 25

        paginator = Paginator(logs, page_size)
        page = paginator.get_page(request.query_params.get("page", 1))

        results = [
            {
                "id": log.id,
                "user": log.user.email if log.user else None,
                "action": log.action,
                "model_name": log.model_name,
                "object_id": log.object_id,
                "description": log.description,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in page
        ]

        return success_response(
            "Audit logs fetched successfully.",
            {
                "results": results,
                "page": page.number,
                "total_pages": paginator.num_pages,
                "total": paginator.count,
            },
        )
