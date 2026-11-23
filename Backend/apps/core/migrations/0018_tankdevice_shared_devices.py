import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_tankdevice_tankdevicerequirement_tankroute'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tankdevice',
            name='device',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tank_links', to='core.devices'),
        ),
        migrations.AddConstraint(
            model_name='tankdevice',
            constraint=models.UniqueConstraint(fields=('tank', 'device'), name='unique_device_per_tank'),
        ),
    ]
