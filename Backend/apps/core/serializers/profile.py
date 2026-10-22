from rest_framework import serializers
from ..models.profiles import UserProfile, DealerProfile


class BaseProfileUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        fields = [
            'first_name',
            'last_name',
            'phone_number',
            'contact_email',
            'address',
            'city',
            'state',
            'pincode',
            'gst_number',
        ]

    def validate(self, attrs):
        if attrs.get('gst_number') is None:
            attrs['gst_number'] = '000000000000000'

        return attrs


class UserProfileUpdateSerializer(BaseProfileUpdateSerializer):

    class Meta(BaseProfileUpdateSerializer.Meta):
        model = UserProfile


class DealerProfileUpdateSerializer(BaseProfileUpdateSerializer):

    class Meta(BaseProfileUpdateSerializer.Meta):
        model = DealerProfile