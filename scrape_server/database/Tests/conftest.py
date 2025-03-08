import os
import django
import pytest

# Set Django settings only once, before any tests are loaded
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrape_server.settings')

# This will be run once at the beginning of the test session
def pytest_configure():
    django.setup() 