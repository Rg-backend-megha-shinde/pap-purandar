from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0017_villagedata_sec24_account_rows'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec25_map_received',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec25_map_rows',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec25_not_received_reason',
            field=models.TextField(blank=True),
        ),
    ]
