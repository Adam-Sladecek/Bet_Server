from django.urls import path
from database.views import (ConfigView, OpportunityView, PreferedOpportunityView, OpportunityChildrenView, 
                            RemoveOpportunityChildView, AddOpportunityChildView, EventView, UsedEventView, 
                            EventOddsView, MarketView, DeleteMarketView)

urlpatterns = [
    path('config', ConfigView.as_view(), name='config'),
    path('opportunity', OpportunityView.as_view(), name='opportunity'),
    path('opportunity/<int:pk>', PreferedOpportunityView.as_view(), name='prefered_opportunity'),
    path('opportunity/children', OpportunityChildrenView.as_view(), name='opportunity_children'),
    path('opportunity/children/<int:pk>', RemoveOpportunityChildView.as_view(), name='remove_opportunity_child'),
    path('opportunity/children/<int:pk>/add/<int:childid>', AddOpportunityChildView.as_view(), name='add_opportunity_children'),
    path('event', EventView.as_view(), name='event'),
    path('event/<int:pk>/odds', EventOddsView.as_view(), name='event_odds'),
    path('event/used/<int:pk>/sportsbook/<int:sbpk>', UsedEventView.as_view(), name='used_event'),
    path('market', MarketView.as_view(), name='market'),
    path('market/<int:pk>', DeleteMarketView.as_view(), name='delete_market'),
]
