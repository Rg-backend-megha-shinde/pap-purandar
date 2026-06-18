from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_alter_processchartcase_unique_together"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name_marathi", models.CharField(max_length=100)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "asset_categories",
                "ordering": ["display_order", "name_marathi"],
            },
        ),
        migrations.CreateModel(
            name="AssetList",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=100)),
                ("name_marathi", models.CharField(max_length=200)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="asset_list", to="app.assetcategory")),
            ],
            options={
                "db_table": "asset_list",
                "ordering": ["category__display_order", "display_order", "name_marathi"],
                "unique_together": {("category", "code")},
            },
        ),
    ]
