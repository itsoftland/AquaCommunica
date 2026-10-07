from rest_framework import status as http_status
from rest_framework.response import Response


def success_response(message, data=None, status=http_status.HTTP_200_OK):
    """Standard success envelope: {"success": true, "message": str, "data": object|null}."""
    return Response(
        {
            "success": True,
            "message": message,
            "data": data,
        },
        status=status,
    )


def error_response(message, data=None, status=http_status.HTTP_400_BAD_REQUEST):
    return Response(
        {
            "success": False,
            "message": message,
            "data": data,
        },
        status=status,
    )

