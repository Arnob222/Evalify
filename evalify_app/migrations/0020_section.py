from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0019_course_faculty_m2m'),
    ]

    operations = [
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('batch', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sections',
                    to='evalify_app.course',
                )),
                ('faculty', models.ManyToManyField(
                    blank=True,
                    limit_choices_to={'role': 'faculty'},
                    related_name='teaching_sections',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('students', models.ManyToManyField(
                    blank=True,
                    limit_choices_to={'role': 'student'},
                    related_name='enrolled_sections',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['batch', 'name'],
                'unique_together': {('course', 'name', 'batch')},
            },
        ),
    ]
