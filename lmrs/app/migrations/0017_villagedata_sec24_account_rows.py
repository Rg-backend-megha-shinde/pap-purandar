from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0016_villagedata_sec21_rows'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec24_account_rows',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
