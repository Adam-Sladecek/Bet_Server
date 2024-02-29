from django.core.management.base import BaseCommand
from scrape_server.database.Scrapes.scripts import populate


class Command(BaseCommand):
    help = 'Run the populate script'

    def handle(self, *args, **options):
        populate()
        self.stdout.write(self.style.SUCCESS('Population script executed successfully.'))
