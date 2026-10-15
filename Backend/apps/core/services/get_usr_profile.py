from ..models.profiles import UserProfile


def get_user_profile(pk):
    """Retrieve a user profile by its primary key.

    Raises ``UserProfile.DoesNotExist`` if no matching profile exists.
    """
    user_profile = UserProfile.objects.get(pk=pk)
    return user_profile
   