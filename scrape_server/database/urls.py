from .views import get_config, set_config, get_opportunities_to_link, set_opportunity_link
from django.urls import path

urlpatterns = [
    path('config/get', get_config, name='configget'),
    path('config/set', set_config, name='configset'),
    path('opportunitytolink/get', get_opportunities_to_link, name='opptolinkget'),
    path('opportunitylink/set', set_opportunity_link, name='set_opportunity_link'),
]
