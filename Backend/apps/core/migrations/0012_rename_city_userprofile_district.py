from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_rename_city_dealerprofile_district'),
    ]

    operations = [
        migrations.RenameField(
            model_name='userprofile',
            old_name='city',
            new_name='district',
        ),
    ]
