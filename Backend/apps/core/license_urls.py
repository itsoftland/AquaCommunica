from django.urls import path
from apps.core.views.license import license_server as ls


urlpatterns = [
    # user profile license urls
    path('register-user-profile/<int:pk>/', ls.RegisterUserProfileWithLicenseServer.as_view(), name="reg_user_profile_with_ls"),
    path('validate-usr-profile-license/<int:pk>/', ls.ValidateUserProfileLicense.as_view(), name='validate_user_profile_license'),
    path('sync-usr-profile-license/<int:pk>/', ls.SyncUserProfileLicense.as_view(), name='sync_user_profile_license'),
    path('sync-usr-profile-license-confirm/<int:pk>/', ls.SyncUserProfileLicenseConfirm.as_view(), name='sync_user_profile_license_confirm'),

    # dealer profile license urls
    path('register-dealer-profile/<int:pk>/', ls.RegisterDealerProfileWithLicenseServer.as_view(), name="reg_dealer_profile_with_ls"),
]
