from django.urls import path
from .views.apk.auth import ProductionLoginView


urlpatterns = [
    path('login/', ProductionLoginView.as_view(), name="production-apk-login"),
]
