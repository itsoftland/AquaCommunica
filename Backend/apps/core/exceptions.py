from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is None:
        return response

    data = response.data

    # Authentication / permission errors
    if isinstance(data, dict) and "detail" in data:

        response.data = {
            "success": False,
            "message": str(data["detail"]),
            "errors": None,
        }

        return response

    # Validation errors
    response.data = {
        "success": False,
        "message": "Validation failed.",
        "errors": data,
    }

    return response