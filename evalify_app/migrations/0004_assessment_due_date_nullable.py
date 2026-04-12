from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0003_question_plos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assessment',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
