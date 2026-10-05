from django.contrib.auth import authenticate, get_user_model

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError



class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": 'password'}
    )

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "Your account is inactive."
            )

        if not user.is_verified:
            raise serializers.ValidationError(
                "Your account is not verified."
            )

        refresh = RefreshToken.for_user(user)

        return {
            "user": user,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }



User = get_user_model()


class UserRegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=6,
        style={"input_type": "password"},
    )

    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    class Meta:

        model = User
        fields = [
            "email",
            "password",
            "password_confirm",
            "role",
            "dealer",
            "parent",
        ]

    def validate_email(self, email):

        email = email.lower().strip()

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
               { "A user with this email already exists."}
            )


        return email


    def validate(self, attrs):

        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        if password != password_confirm:
            raise serializers.ValidationError(
                {
                    "password_confirm": "Passwords do not match."
                }
            )

        return attrs


    def create(self, validated_data):

        # Remove password_confirm because it is
        # only used for validation
        validated_data.pop("password_confirm")

        # Remove password so we can hash it properly
        password = validated_data.pop("password")

        # Use CustomUserManager.create_user()
        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        return user


class LogoutSerializer(serializers.Serializer):

    refresh = serializers.CharField()

    def validate(self, attrs):

        self.token = attrs["refresh"]

        return attrs

    def save(self, **kwargs):

        try:
            refresh_token = RefreshToken(self.token)
            refresh_token.blacklist()
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "Invalid or expired refresh token."}
            )
