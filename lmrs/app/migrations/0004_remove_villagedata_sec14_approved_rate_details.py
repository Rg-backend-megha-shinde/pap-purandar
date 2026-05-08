from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_villagedata_sec14_approved_rate_details'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='villagedata',
            name='sec14_approved_rate_details',
        ),
    ]
