from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = 'Initializes required user groups'

    def handle(self, *args, **kwargs):
        # List of groups to ensure exist
        groups = ["Finance", "Admin", "CEO", "PetrolCard"]

        for group_name in groups:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created group "{group_name}"'))
            else:
                self.stdout.write(f'Group "{group_name}" already exists')
