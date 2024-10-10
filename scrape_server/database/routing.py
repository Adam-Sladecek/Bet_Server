from django.urls import re_path
from database.consumers import ScrapeConsumer

websocket_urlpatterns = [
    re_path('ws/scrape/', ScrapeConsumer.as_asgi()),
]