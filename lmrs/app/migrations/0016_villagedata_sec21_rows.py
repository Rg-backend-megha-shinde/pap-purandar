from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0015_villagedata_sec11_patra_kramank'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec21_rows',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
