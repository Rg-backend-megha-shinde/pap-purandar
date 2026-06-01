from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0023_alter_inspection_unique_together'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='landrecord712',
            index=models.Index(fields=['district'], name='app_landrec_distri_4bc4cd_idx'),
        ),
        migrations.AddIndex(
            model_name='landrecord712',
            index=models.Index(fields=['taluka'], name='app_landrec_taluka_5f3105_idx'),
        ),
        migrations.AddIndex(
            model_name='landrecord712',
            index=models.Index(fields=['village'], name='app_landrec_village_9ddc14_idx'),
        ),
        migrations.AddIndex(
            model_name='landrecord712',
            index=models.Index(fields=['gut_number'], name='app_landrec_gut_num_d2f6f3_idx'),
        ),
        migrations.AddIndex(
            model_name='landrecord712',
            index=models.Index(fields=['khata_number'], name='app_landrec_khata_n_845f95_idx'),
        ),
        migrations.AddIndex(
            model_name='landrecord712',
            index=models.Index(fields=['district', 'taluka', 'village'], name='app_landrec_distri_d8346b_idx'),
        ),
        migrations.AddIndex(
            model_name='landrecord712',
            index=models.Index(fields=['district', 'taluka', 'village', 'gut_number', 'khata_number'], name='app_landrec_distri_95b175_idx'),
        ),
    ]
