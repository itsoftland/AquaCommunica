from django.db.models.signals import post_save
from django.dispatch import receiver


from ..models.customuser import CustomUser
from ..models.profiles import UserProfile


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):

    if created and instance.role == CustomUser.Role.USER_ADMIN:

        created_by_instance = instance.created_by
        print("===============================================")
        print(created_by_instance)
        print("===============================================")
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

        


