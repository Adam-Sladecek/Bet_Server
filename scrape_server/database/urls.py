from .views import (delete_opportunity_link, get_config, set_config, get_opportunities_to_link, 
                    add_parent_opportunities, get_opportunity_links, add_child_to_parent_opportunity,
                    get_opportunity_children, remove_child_from_parent_opportunity)
from django.urls import path

urlpatterns = [
    path('config/get', get_config, name='configget'),
    path('config/set', set_config, name='configset'),
    path('opportunitytolink/get', get_opportunities_to_link, name='opptolinkget'),
    path('opportunitylink/add', add_parent_opportunities, name='add_parent_opportunities'),
    path('opportunity/<int:parentid>/add/<int:childid>', add_child_to_parent_opportunity, name='add_child_to_parent_opportunity'),
    path('opportunity/children/get', get_opportunity_children, name='get_opportunity_children'),
    path('opportunity/children/remove/<int:pk>', remove_child_from_parent_opportunity, name='remove_child_from_parent_opportunity'),
    path('opportunitylink/get', get_opportunity_links, name='get_opportunity_links'),
    path('opportunitylink/delete/<int:pk>', delete_opportunity_link, name='delete_opportunity_link'),
]
