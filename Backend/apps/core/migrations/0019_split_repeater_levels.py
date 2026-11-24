from django.db import migrations, models


def repeater_to_l1(apps, schema_editor):
    for model, field in (('Devices', 'device_type'), ('TankDeviceRequirement', 'device_type')):
        apps.get_model('core', model).objects.filter(**{field: 'repeater'}).update(**{field: 'repeater_l1'})


def l1_to_repeater(apps, schema_editor):
    for model, field in (('Devices', 'device_type'), ('TankDeviceRequirement', 'device_type')):
        apps.get_model('core', model).objects.filter(**{field + '__in': ['repeater_l1', 'repeater_l2']}).update(**{field: 'repeater'})


CHOICES = [
    ('repeater_l1', 'Repeater Level 1'), ('repeater_l2', 'Repeater Level 2'),
    ('transmitter', 'Transmitter'), ('receiver', 'Receiver'),
    ('gateway', 'Gateway'), ('pump_controller', 'Pump Controller'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_tankdevice_shared_devices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devices', name='device_type',
            field=models.CharField(choices=CHOICES, db_index=True, default='transmitter', max_length=20),
        ),
        migrations.AlterField(
            model_name='tankdevicerequirement', name='device_type',
            field=models.CharField(choices=CHOICES, default='repeater_l1', max_length=20),
        ),
        migrations.RunPython(repeater_to_l1, l1_to_repeater),
    ]
