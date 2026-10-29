from rest_framework import serializers
from rest_framework import status

from ..models.customuser import CustomUser
from ..utlis.responses import error_response


class ChangePasswordSerializer(serializers.Serializer):

    current_password = serializers.CharField(
        required=True,
        write_only=True
    )

    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=6,
    )

    confirm_password = serializers.CharField(
        required=True,
        write_only=True
    )


    def validate(self, attrs):

        user = self.context.get('request').user

        current_password = attrs.get('current_password')

        if not user.check_password(current_password):

            raise serializers.ValidationError(
                {
                    "Incorrect current password"
                }
            )

        if attrs['new_password'] != attrs['confirm_password']:

            raise serializers.ValidationError(
                {
                    "New Password : Confirm Password not matching"
                }
            )

        if user.check_password(attrs['new_password']):

            raise serializers.ValidationError(
                {
                    "can't use current password as new password"
                }
            )

        return attrs


    def save(self, **kwargs):

        user = self.context.get('request').user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])

        return user


class AdminSetPasswordSerializer(serializers.Serializer):
    """Set another user's password; the caller's rights are checked in the view."""

    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=6,
    )

    confirm_password = serializers.CharField(
        required=True,
        write_only=True
    )

    def validate(self, attrs):

        if attrs['new_password'] != attrs['confirm_password']:

            raise serializers.ValidationError(
                {
                    "confirm_password": "New Password : Confirm Password not matching"
                }
            )

        return attrs


class CustomUserListSerializer(serializers.ModelSerializer):

    role_display = serializers.CharField(
        source='get_role_display',
        read_only=True
    )

    dealer_email = serializers.EmailField(
        source='dealer.email',
        read_only=True,
        default=None
    )

    created_by_email = serializers.EmailField(
        source='created_by.email',
        read_only=True,
        default=None
    )

    client_type = serializers.CharField(
        source='user_profile.client_type',
        read_only=True,
        default=None
    )

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'role_display',
            'dealer',
            'dealer_email',
            'client_type',
            'user_admin',
            'created_by',
            'created_by_email',
            'is_active',
            'is_verified',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
