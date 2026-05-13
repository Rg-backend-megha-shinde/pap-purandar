from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0012_villagedata_notified_area_rows'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec3_rows',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
