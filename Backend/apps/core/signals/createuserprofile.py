import logging

from django.db.models.signals import post_save
from django.dispatch import receiver


from ..models.customuser import CustomUser
from ..models.profiles import UserProfile, DealerProfile


log_profile = logging.getLogger('aquacommunica.profilelog')

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):

    log_profile.info(
        "CustomUser post_save signal triggered | "
        "user_id=%s | email=%s | role=%s | created=%s",
        instance.id,
        instance.email,
        instance.role,
        created,
    )

    if created: 

        created_by_instance = instance.created_by
        
        if instance.role == CustomUser.Role.USER_ADMIN:

            dealer_instance = instance.dealer

            if dealer_instance is not None:
                client_type = "dealer"
            else:
                client_type = "direct"
                dealer_instance = None

            UserProfile.objects.create(
                user=instance,
                client_type=client_type,
                dealer=dealer_instance,
                created_by=created_by_instance,
            )

        elif instance.role == CustomUser.Role.DEALER:

            DealerProfile.objects.create(
                user=instance,
                created_by=created_by_instance,
            )


        log_profile.info(
            "Profile Created Successfully | "
            "user_id=%s | eamail=%s | role=%s",
            instance.id,
            instance.email,
            instance.role,
        )


