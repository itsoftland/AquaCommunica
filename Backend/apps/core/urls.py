from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.core.serializers.auth import SessionTokenRefreshSerializer
from apps.core.views.web import auth, users, profile


urlpatterns = [
    # authemtication urls
    path('login/', auth.LoginView.as_view(), name="login"),
    path('token/refresh/', TokenRefreshView.as_view(serializer_class=SessionTokenRefreshSerializer), name="token_refresh"),
    path('user-profile/', auth.ProfileView.as_view(), name="user_profile"),
    path('create-user/', auth.UserRegisterView.as_view(), name="user_registration"),
    path('logout/', auth.LogoutView.as_view(), name="logout"),

    #user urls
    path('user/<int:pk>/hard-delete/', users.PermanentUserDelete.as_view(), name="user_hard_delete"),
    path('user/<int:pk>/soft-delete/', users.SoftDeleteUser.as_view(), name="user_soft_delete"),
    path('user/change-password/', users.ChangePassword.as_view(), name="change_password"),

    #user profile urls
    path('userprofile/<int:pk>/update/', profile.UpdateUserProfile.as_view(), name="update_user_profile"),
]
