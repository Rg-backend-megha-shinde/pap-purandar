from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_villagedata_sec25_map_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec1_total_notified_area',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]

