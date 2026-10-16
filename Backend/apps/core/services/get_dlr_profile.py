from ..models.profiles import DealerProfile


def get_dealer_profile(pk):
    """Retrieve a dealer profile by its primary key.

    Raises ``DealerProfile.DoesNotExist`` if no matching profile exists.
    """
    dealer_profile = DealerProfile.objects.get(pk=pk)
    return dealer_profile
   