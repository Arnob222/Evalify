from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0022_section_code_and_content_sections'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('faculty', 'Faculty'),
                    ('student', 'Student'),
                    ('admin', 'Admin'),
                    ('dao', 'DAO'),
                    ('dept_head', 'Department Head'),
                ],
                default='',
                max_length=20,
            ),
        ),
    ]
