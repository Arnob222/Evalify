from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_faculty_fk_to_m2m(apps, schema_editor):
    Course = apps.get_model('evalify_app', 'Course')
    db_alias = schema_editor.connection.alias
    for course in Course.objects.using(db_alias).all():
        old_id = course.faculty_old_id
        if old_id:
            course.faculty.add(old_id)


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0018_doa_role'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add is_active field
        migrations.AddField(
            model_name='course',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        # Rename old FK so we can add M2M with the same name 'faculty'
        migrations.RenameField(
            model_name='course',
            old_name='faculty',
            new_name='faculty_old',
        ),
        # Change related_name of old FK to avoid clash with the new M2M
        migrations.AlterField(
            model_name='course',
            name='faculty_old',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='courses_fk_old',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Add new M2M field
        migrations.AddField(
            model_name='course',
            name='faculty',
            field=models.ManyToManyField(
                blank=True,
                related_name='courses',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Copy FK data into M2M
        migrations.RunPython(copy_faculty_fk_to_m2m, migrations.RunPython.noop),
        # Remove old FK column
        migrations.RemoveField(
            model_name='course',
            name='faculty_old',
        ),
    ]
