from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="treedetail",
            name="valuation",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
