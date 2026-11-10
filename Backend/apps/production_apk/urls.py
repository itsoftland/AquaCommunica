from django.urls import path
from .views.apk import auth, device


urlpatterns = [
    # production user login
    path('login/', auth.ProductionLoginView.as_view(), name="production-apk-login"),

    # device
    path('register-device/', device.RegisterDeviceView.as_view(), name='register_device'),
]
