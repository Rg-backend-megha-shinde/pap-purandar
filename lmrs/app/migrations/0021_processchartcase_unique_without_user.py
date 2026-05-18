from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0020_villagedata_notified_area_totals_by_section'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='processchartcase',
            unique_together=set(),
        ),
    ]
