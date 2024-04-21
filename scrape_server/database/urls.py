from .views import delete_event, get_config
from django.urls import path

urlpatterns = [
    path('delete-event/', delete_event, name='delete-event'),
    path('config/', get_config, name='config'),
]
