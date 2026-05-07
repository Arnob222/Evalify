from django.db import migrations


class Migration(migrations.Migration):
    # Tables were already created by 0015_escar_action_plans (which depends on
    # 0014_course_enrollment_code). This migration is kept as a no-op so that
    # production databases with it recorded as applied remain consistent.
    dependencies = [
        ('evalify_app', '0015_escar_action_plans'),
    ]

    operations = []
