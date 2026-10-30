from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.core.serializers.auth import SessionTokenRefreshSerializer
from apps.core.views.web import auth, users, profile, audit


urlpatterns = [
    # authemtication urls
    path('login/', auth.LoginView.as_view(), name="login"),
    path('token/refresh/', TokenRefreshView.as_view(serializer_class=SessionTokenRefreshSerializer), name="token_refresh"),
    path('user-profile/', auth.ProfileView.as_view(), name="user_profile"),
    path('create-user/', auth.UserRegisterView.as_view(), name="user_registration"),
    path('logout/', auth.LogoutView.as_view(), name="logout"),
    path('dashboard/', auth.DashboardView.as_view(), name="dashboard_stats"),

    #user urls
    path('user/<int:pk>/hard-delete/', users.PermanentUserDelete.as_view(), name="user_hard_delete"),
    path('user/<int:pk>/soft-delete/', users.SoftDeleteUser.as_view(), name="user_soft_delete"),
    path('user/<int:pk>/restore/', users.RestoreUser.as_view(), name="user_restore"),
    path('user/<int:pk>/set-password/', users.AdminChangeUserPassword.as_view(), name="user_set_password"),
    path('user/change-password/', users.ChangePassword.as_view(), name="change_password"),
    path('list-users/', users.ListUsers.as_view(), name="users_list"),

    #user profile urls
    path('userprofile/<int:pk>/update/', profile.UpdateUserProfile.as_view(), name="update_user_profile"),
    path('get-user-profile-list/', profile.ListUserProfiles.as_view(), name="get_user_profile_list"),
    path('user-profile-detailes/<int:pk>/', profile.UserProfileDetailes.as_view(), name="user_profile_details"),

    # audit logs (superadmin only)
    path('audit-logs/', audit.AuditLogListView.as_view(), name="audit_logs"),

    # dealer profile update
    path('dealerprofile/<int:pk>/update/', profile.UpdateDealerProfile.as_view(), name="update_dealer_profile"),
    path('get-dealer-profile-list/', profile.ListDealerProfiles.as_view(), name="get_dealer_profile_list"),
    path('dealer-profile-details/<int:pk>/', profile.DealerProfileDetails.as_view(), name="dealer_profile_details"),

]
