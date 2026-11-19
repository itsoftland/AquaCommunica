import logging

from rest_framework.exceptions import NotFound

from ..models.tank import Tank


action_log = logging.getLogger('aquacommunica.action.log')


def get_tank(pk):
    """Retrieve a tank by its primary key.

    Raises ``rest_framework.exceptions.NotFound`` if no matching tank exists.
    """
    try:
        tank = Tank.objects.select_related(
            'user_profile',
            'transmitter',
            'created_by'
        ).get(pk=pk)

    except Tank.DoesNotExist:
        action_log.warning("Tank not found | tank_id=%s", pk)
        raise NotFound("Tank not found")

    return tank
