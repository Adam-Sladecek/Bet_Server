from .views import get_config, set_config
from django.urls import path

urlpatterns = [
    path('config/get', get_config, name='configget'),
    path('config/set', set_config, name='configset'),
]
