from django.contrib import admin
from .models import (
    Sport,
    SportType,
    Sportsbook,
    Event,
    EventLink,
    ParentOpportunity,
    Odd,
    OddLink,
    ArbitrageBet,
    ArbitrageBetDetail,
    Opportunity
)
admin.site.register(Sport)
admin.site.register(SportType)
admin.site.register(Sportsbook)
admin.site.register(Event)
admin.site.register(EventLink)
admin.site.register(ParentOpportunity)
admin.site.register(Odd)
admin.site.register(OddLink)
admin.site.register(ArbitrageBet)
admin.site.register(ArbitrageBetDetail)
admin.site.register(Opportunity)