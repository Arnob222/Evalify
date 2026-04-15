from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0006_studymaterial_video_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('notif_type', models.CharField(
                    choices=[
                        ('grade_released',    'Grade Released'),
                        ('deadline_tomorrow', 'Deadline Tomorrow'),
                        ('deadline_today',    'Due Today'),
                        ('new_assignment',    'New Assignment'),
                        ('new_material',      'New Material'),
                        ('announcement',      'Announcement'),
                    ],
                    max_length=30,
                )),
                ('title',      models.CharField(max_length=200)),
                ('message',    models.TextField()),
                ('is_read',    models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('course', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='evalify_app.course',
                )),
                ('assessment', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='evalify_app.assessment',
                )),
                ('submission', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='evalify_app.submission',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]