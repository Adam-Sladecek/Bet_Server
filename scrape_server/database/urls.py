from .views import delete_event, get_config, set_config
from django.urls import path

urlpatterns = [
    path('delete-event/', delete_event, name='delete-event'),
    path('config/get', get_config, name='configget'),
    path('config/set', set_config, name='configset'),
]
