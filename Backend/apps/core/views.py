from django.http import JsonResponse


def demo(request):
    return JsonResponse({
        "status": "success",
        "message": "AquaCommunica Backend is working!",
        "app": "core",
        "version": "1.0.0"
    })