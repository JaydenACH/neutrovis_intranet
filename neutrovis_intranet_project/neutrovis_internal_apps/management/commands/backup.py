from django.core.management.base import BaseCommand
from django.utils import timezone
import os
from dotenv import load_dotenv


load_dotenv()


class Command(BaseCommand):
    help = 'Dump all data to a JSON file with a unique name based on the current date'

    def handle(self, *args, **kwargs):
        current_datetime = timezone.now().strftime('%Y-%m-%d_%H:%M:%S')
        file_name = f'backup_live_{current_datetime}.json'
        env_backup_url = os.environ.get("BACKUP_URL", False)
        backup_path = os.path.join(env_backup_url, file_name)

        os.system(f'python manage.py dumpdata --all > {backup_path}')

        self.stdout.write(self.style.SUCCESS(f'Backup created: {backup_path}'))
