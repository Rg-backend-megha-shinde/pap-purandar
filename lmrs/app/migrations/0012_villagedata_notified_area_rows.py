from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0011_villagedata_sec1_admin_approvals"),
    ]

    operations = [
        migrations.AddField(
            model_name="villagedata",
            name="notified_area_rows",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
