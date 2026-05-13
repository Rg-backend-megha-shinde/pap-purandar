from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0013_villagedata_sec3_rows'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec13_rows',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec14_rows',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec16_rows',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec17_rows',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec18_rows',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec19_rows',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='sec20_rows',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
