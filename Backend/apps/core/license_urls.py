from django.urls import path
from apps.core.views.license import license_server as ls


urlpatterns = [
    # user profile license urls
    path('register-user-profile/<int:pk>/', ls.RegisterUserProfileWithLicenseServer.as_view(), name="reg_user_profile_with_ls"),
]
