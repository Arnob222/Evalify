from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0013_subquestion_grades'),
    ]

    operations = [
        migrations.CreateModel(
            name='CLOActionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_plan', models.TextField(blank=True, default='')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clo_action_plans', to='evalify_app.course')),
                ('clo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='action_plans', to='evalify_app.clo')),
            ],
            options={
                'unique_together': {('course', 'clo')},
            },
        ),
        migrations.CreateModel(
            name='PLOActionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_plan', models.TextField(blank=True, default='')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plo_action_plans', to='evalify_app.course')),
                ('plo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='action_plans', to='evalify_app.plo')),
            ],
            options={
                'unique_together': {('course', 'plo')},
            },
        ),
    ]
