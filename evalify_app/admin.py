from django.core.management.base import BaseCommand
from evalify_app.models import User


class Command(BaseCommand):
    help = 'Create the default admin user'

    def handle(self, *args, **options):
        email    = 'admin@uap-bd.edu'
        password = '123456789'
        username = 'admin'

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'Admin already exists: {email}'))
            return

        base = username
        i = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{i}'
            i += 1

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name='System Admin',
            role='admin',
            is_staff=True,
        )
        self.stdout.write(self.style.SUCCESS('Admin created! Email: admin@uap-bd.edu | Password: 123456789'))