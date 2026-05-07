import re
from django.db import migrations, models


def generate_section_codes(apps, schema_editor):
    Section = apps.get_model('evalify_app', 'Section')
    used = set()
    for sec in Section.objects.select_related('course').order_by('id'):
        clean = re.sub(r'[^A-Z0-9]', '', sec.course.code.upper())
        parts = sec.batch.split()
        if len(parts) >= 2:
            batch_short = parts[0][0].upper() + parts[1][-2:]
        else:
            batch_short = sec.batch[:3].upper()
        base = f"{clean}-{sec.name.upper()}-{batch_short}"
        code, i = base, 1
        while code in used:
            code = f"{base}-{i}"
            i += 1
        sec.code = code
        sec.save(update_fields=['code'])
        used.add(code)


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0021_rename_doa_to_dao'),
    ]

    operations = [
        # 1. Add code to Section (non-unique first so existing rows can be populated)
        migrations.AddField(
            model_name='section',
            name='code',
            field=models.CharField(max_length=20, blank=True, default=''),
            preserve_default=False,
        ),
        # 2. Populate codes for existing sections
        migrations.RunPython(generate_section_codes, migrations.RunPython.noop),
        # 3. Now enforce uniqueness
        migrations.AlterField(
            model_name='section',
            name='code',
            field=models.CharField(max_length=20, unique=True, blank=True),
        ),
        # 4. Add sections M2M to Assessment
        migrations.AddField(
            model_name='assessment',
            name='sections',
            field=models.ManyToManyField(
                blank=True,
                related_name='targeted_assessments',
                to='evalify_app.section',
            ),
        ),
        # 5. Add sections M2M to StudyMaterial
        migrations.AddField(
            model_name='studymaterial',
            name='sections',
            field=models.ManyToManyField(
                blank=True,
                related_name='targeted_materials',
                to='evalify_app.section',
            ),
        ),
        # 6. Add sections M2M to Announcement
        migrations.AddField(
            model_name='announcement',
            name='sections',
            field=models.ManyToManyField(
                blank=True,
                related_name='targeted_announcements',
                to='evalify_app.section',
            ),
        ),
    ]
