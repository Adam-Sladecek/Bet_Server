from .views import (get_config, set_config, get_opportunities_to_link, add_child_to_parent_opportunity,
                    get_opportunity_children, remove_child_from_parent_opportunity, change_monitored_events,
                    change_event_odds, get_monitored_events, get_event_odds, set_prefered_opportunity,
                    get_all_markets, add_market, remove_market, set_used_event)
from django.urls import path

urlpatterns = [
    path('config/get', get_config, name='configget'),
    path('config/set', set_config, name='configset'),
    path('opportunitytolink/get', get_opportunities_to_link, name='opptolinkget'),
    path('opportunity/<int:parentid>/add/<int:childid>', add_child_to_parent_opportunity, name='add_child_to_parent_opportunity'),
    path('opportunity/children/get', get_opportunity_children, name='get_opportunity_children'),
    path('opportunity/children/remove/<int:pk>', remove_child_from_parent_opportunity, name='remove_child_from_parent_opportunity'),
    path('opportunity/prefered/<int:pk>', set_prefered_opportunity, name='set_prefered_opportunity'),
    path('event', get_monitored_events, name='get_monitored_events'),
    path('event/update', change_monitored_events, name='change_monitored_events'),
    path('event/used/<int:pk>/sportsbook/<int:sbpk>', set_used_event, name='set_used_event'),
    path('event/<int:pk>/odds', get_event_odds, name='get_event_odds'),
    path('event/<int:pk>/odds/update', change_event_odds, name='change_event_odds'),
    path('market', get_all_markets, name='get_all_markets'),
    path('market/add', add_market, name='add_market'),
    path('market/remove/<int:pk>', remove_market, name='remove_market'),
]
