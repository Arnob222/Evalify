from django.db import migrations, models


def rename_doa_to_dao(apps, schema_editor):
    User = apps.get_model('evalify_app', 'User')
    User.objects.filter(role='doa').update(role='dao')


def rename_dao_to_doa(apps, schema_editor):
    User = apps.get_model('evalify_app', 'User')
    User.objects.filter(role='dao').update(role='doa')


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0020_section'),
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
                ],
                default='',
                max_length=20,
            ),
        ),
        migrations.RunPython(rename_doa_to_dao, rename_dao_to_doa),
    ]
