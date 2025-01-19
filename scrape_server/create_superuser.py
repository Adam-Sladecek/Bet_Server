import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrape_server.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()

def create_superuser():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    try:
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            print(f'Superuser {username} created successfully!')
        else:
            print(f'Superuser {username} already exists.')
    except IntegrityError as e:
        print(f'Error creating superuser: {e}')

if __name__ == "__main__":
    create_superuser() 