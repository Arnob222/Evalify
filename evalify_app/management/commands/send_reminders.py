from django.core.management.base import BaseCommand
from evalify_app.notifications import send_deadline_reminders
 
 
class Command(BaseCommand):
    help = 'Send deadline reminder notifications to students'
 
    def handle(self, *args, **kwargs):
        send_deadline_reminders()
        self.stdout.write(self.style.SUCCESS('✅ Deadline reminders sent!'))
 