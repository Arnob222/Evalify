from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='submitted_file',
            field=models.FileField(blank=True, null=True, upload_to='submissions/'),
        ),
    ]
