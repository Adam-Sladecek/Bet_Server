from django.urls import path
from .views import start_scrape, end_scrape, delete_event

urlpatterns = [
    path('start/', start_scrape, name='start_scrape'),
    path('end/', end_scrape, name='end_scrape'),
    path('delete-event/', delete_event, name='delete-event'),
]