from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0019_villagedata_sec1_total_notified_area'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='notified_area_totals_by_section',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

