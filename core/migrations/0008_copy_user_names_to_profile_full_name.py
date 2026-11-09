from django.conf import settings
from django.db import migrations


def copy_names_to_full_name(apps, schema_editor):
    Profile = apps.get_model('core', 'Profile')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))

    for profile in Profile.objects.select_related('user'):
        if (profile.full_name or '').strip():
            continue
        user = profile.user
        if user is None:
            continue
        parts = [
            part.strip()
            for part in (user.first_name, user.last_name)
            if part and part.strip()
        ]
        if not parts:
            continue
        profile.full_name = ' '.join(parts)
        profile.save(update_fields=['full_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_alter_followupevaluation_evaluator_and_more'),
    ]

    operations = [
        migrations.RunPython(
            copy_names_to_full_name, migrations.RunPython.noop
        ),
    ]
