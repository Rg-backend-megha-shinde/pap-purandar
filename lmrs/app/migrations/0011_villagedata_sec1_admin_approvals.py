from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_alter_villagedata_sec14_approved_rate_details_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec1_admin_approvals',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
