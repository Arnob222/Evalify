from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0005_studymaterial'),
    ]

    operations = [
        migrations.AddField(
            model_name='studymaterial',
            name='material_type',
            field=models.CharField(
                choices=[
                    ('lecture_note', 'Lecture Note'),
                    ('reference',    'Reference Material'),
                    ('video',        'Reference Video'),
                    ('assignment',   'Assignment Sheet'),
                    ('other',        'Other'),
                ],
                default='lecture_note',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='studymaterial',
            name='video_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='studymaterial',
            name='is_visible',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='studymaterial',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='materials/'),
        ),
    ]