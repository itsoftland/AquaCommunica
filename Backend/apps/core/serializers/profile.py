from rest_framework import serializers
from ..models.profiles import UserProfile, DealerProfile

DEFAULT_GST_NUMBER = '000000000000000'


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
        if 'gst_number' in attrs:
            gst = attrs['gst_number']
            if gst is None or not str(gst).strip():
                attrs['gst_number'] = DEFAULT_GST_NUMBER
        elif not (self.instance and self.instance.gst_number):
            attrs['gst_number'] = DEFAULT_GST_NUMBER

        return attrs


class UserProfileDisplaySerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    dealer_email = serializers.EmailField(source='dealer.email', read_only=True, default=None)

    class Meta:
        model = UserProfile
        fields = [
            'id',
            'user',
            'user_email',
            'profile_id',
            'product_registration_id',
            'unique_identifier',
            'first_name',
            'last_name',
            'phone_number',
            'contact_email',
            'address',
            'city',
            'state',
            'pincode',
            'gst_number',
            'client_type',
            'dealer',
            'dealer_email',
            'authentication_status',
            'is_profile_active',
            'validity_from_date',
            'validity_to_date',
            'total_licence_unit',
            'total_user_count',
            'parent_user_count',
            'child_user_count',
            'total_device_count',
            'error_message',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class UserProfileUpdateSerializer(BaseProfileUpdateSerializer):

    class Meta(BaseProfileUpdateSerializer.Meta):
        model = UserProfile


class DealerProfileUpdateSerializer(BaseProfileUpdateSerializer):

    class Meta(BaseProfileUpdateSerializer.Meta):
        model = DealerProfile