from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_add_missing_documentmaster_land_record_id'),
        ('app', '0002_villagedata_sec3_upvibhag_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec14_approved_rate_details',
            field=models.TextField(blank=True),
        ),
    ]
