from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from database.views import (ConfigView, OpportunityView, PreferredOpportunityView, OpportunityChildrenView, 
                            RemoveOpportunityChildView, AddOpportunityChildView, EventView, UsedEventView, 
                            EventOddsView, MarketView, DeleteMarketView)

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('configs', ConfigView.as_view(), name='config'),
    path('opportunities', OpportunityView.as_view(), name='opportunity'),
    path('opportunities/<int:pk>', PreferredOpportunityView.as_view(), name='preferred_opportunity'),
    path('opportunities/children', OpportunityChildrenView.as_view(), name='opportunity_children'),
    path('opportunities/<int:pk>/children', RemoveOpportunityChildView.as_view(), name='remove_opportunity_child'),
    path('opportunities/<int:pk>/children/<int:childid>', AddOpportunityChildView.as_view(), name='add_opportunity_children'),
    path('events', EventView.as_view(), name='event'),
    path('events/<int:pk>/odds', EventOddsView.as_view(), name='event_odds'),
    path('events/<int:pk>/used/<int:sbpk>', UsedEventView.as_view(), name='used_event'),
    path('markets', MarketView.as_view(), name='market'),
    path('markets/<int:pk>', DeleteMarketView.as_view(), name='delete_market'),
]
