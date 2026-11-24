from django.db import migrations


def dedupe_transmitters(apps, schema_editor):
    """Before making Tank.transmitter one-to-one: when several tanks share a
    transmitter, keep it on one tank (an active one first, else the oldest)
    and clear it on the others so they can be re-configured."""
    Tank = apps.get_model('core', 'Tank')
    seen = set()
    for tank in Tank.objects.exclude(transmitter__isnull=True).order_by('-is_active', 'id'):
        if tank.transmitter_id in seen:
            Tank.objects.filter(pk=tank.pk).update(transmitter=None)
        else:
            seen.add(tank.transmitter_id)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_split_repeater_levels'),
    ]

    operations = [
        migrations.RunPython(dedupe_transmitters, migrations.RunPython.noop),
    ]
