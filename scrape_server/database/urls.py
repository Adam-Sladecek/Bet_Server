from .views import (get_config, set_config, get_opportunities_to_link, add_child_to_parent_opportunity,
                    get_opportunity_children, remove_child_from_parent_opportunity, change_monitored_events,
                    change_event_odds, get_monitored_events)
from django.urls import path

urlpatterns = [
    path('config/get', get_config, name='configget'),
    path('config/set', set_config, name='configset'),
    path('opportunitytolink/get', get_opportunities_to_link, name='opptolinkget'),
    path('opportunity/<int:parentid>/add/<int:childid>', add_child_to_parent_opportunity, name='add_child_to_parent_opportunity'),
    path('opportunity/children/get', get_opportunity_children, name='get_opportunity_children'),
    path('opportunity/children/remove/<int:pk>', remove_child_from_parent_opportunity, name='remove_child_from_parent_opportunity'),
    path('event', get_monitored_events, name='get_monitored_events'),
    path('event/update', change_monitored_events, name='change_monitored_events'),
    path('event/<int:event_pk>/odds/update', change_event_odds, name='change_event_odds'),
]
