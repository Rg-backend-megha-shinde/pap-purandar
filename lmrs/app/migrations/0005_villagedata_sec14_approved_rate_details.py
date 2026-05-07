from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_remove_villagedata_sec14_approved_rate_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec14_approved_rate_details',
            field=models.TextField(blank=True),
        ),
    ]
