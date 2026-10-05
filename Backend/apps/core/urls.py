from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.core.views.web import auth


urlpatterns = [
    # authemtication urls
    path('auth/login/', auth.LoginView.as_view(), name="login"),
    path('auth/token/refresh', TokenRefreshView.as_view(), name="token_refresh"),
]
