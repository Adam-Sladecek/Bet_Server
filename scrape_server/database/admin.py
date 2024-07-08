from django.contrib import admin
from .models import (
    Sport,
    Sportsbook,
    Event,
    Odd,
    Opportunity
)
admin.site.register(Sport)
admin.site.register(Sportsbook)
admin.site.register(Event)
admin.site.register(Odd)
admin.site.register(Opportunity)