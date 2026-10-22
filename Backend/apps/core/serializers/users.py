from rest_framework import serializers
from rest_framework import status

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
    
