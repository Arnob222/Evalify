from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0002_submission_submitted_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='plos',
            field=models.ManyToManyField(blank=True, to='evalify_app.plo'),
        ),
    ]
