from __future__ import annotations
from django.db import models
from fuzzywuzzy import fuzz

class Sport(models.Model):
    name = models.CharField(max_length=20, unique=True)
    selected = models.BooleanField(default=False)
    class Meta:
        app_label = 'database'

class Sportsbook(models.Model):
    name = models.CharField(max_length=30, unique=True)
    is_default = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    class Meta:
        app_label = 'database'

class SportsbookMarket(models.Model):
    value = models.CharField(max_length=50)
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE, related_name='markets')
    class Meta:
        app_label = 'database'
        
class Event(models.Model):
    event_id = models.IntegerField()
    time = models.CharField(max_length=60)
    home = models.CharField(max_length=50)
    away = models.CharField(max_length=50)
    is_default = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    used = models.BooleanField(default=False)
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', default=None)
    class Meta:
        app_label = 'database'

    def add_parent(self, parent: Event) -> None:
        if parent.sport != self.sport: 
            raise ValueError(f"Sport mismatch. Parent: {self.sport.name}, Event: {parent.sport.name}.")
        if not parent.is_default: 
            raise ValueError(f"Parent must be from default sportsbook.")
        self.parent = parent

    def get_score(self, event: Event) -> float:
        ratio1= (fuzz.token_sort_ratio(self.home.lower(), event.home.lower()) +
                    fuzz.token_sort_ratio(self.away.lower(), event.away.lower())) / 2.0
        ratio2= (fuzz.token_sort_ratio(self.home.lower(), event.away.lower()) +
                    fuzz.token_sort_ratio(self.away.lower(), event.home.lower())) / 2.0
        
        return max(ratio1, ratio2)
    
class Price(models.Model):
    price_id = models.BigIntegerField()
    movement= models.IntegerField(default=0)
    odds = models.DecimalField(max_digits=10, decimal_places=3)
    is_default = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='prices')
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', default=None)
    class Meta:
        app_label = 'database'

    def add_parent(self, parent: Price) -> None:
        if not parent.is_default: 
            raise ValueError(f"Parent must be from default sportsbook.")
        self.parent = parent

    def can_be_linked(self, price: Price) -> bool:
        return self.opportunity.parent == price.opportunity
    
    def should_be_updated(self) -> bool:
        return self.movement != 0
    
    def ev(self, parent_odds: float) -> float: 
        impl_prob = 1/parent_odds
        ev = (impl_prob * (float(self.odds) - 1)) - (1 - impl_prob)
        return round(100 * ev, 2)
    
    def stake(self, parent_odds: float) -> float: 
        odds_float = float(self.odds)
        if odds_float == 1: 
            return 0.0
        impl_prob = 1 / parent_odds
        kelly = impl_prob - (1 - impl_prob) / (odds_float - 1)
        return round(kelly, 2)
    
class Opportunity(models.Model):
    description = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)
    prefered = models.BooleanField(default=False)
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', default=None)
    class Meta:
        app_label = 'database'
        indexes = [
            models.Index(fields=['sportsbook_id', 'sport_id']),
        ]

    def add_parent(self, parent: Opportunity) -> None:
        if self.is_default: 
            raise ValueError(f"Child can not be from default sportsbook.")
        if parent.sport != self.sport: 
            raise ValueError(f"Sport mismatch. Parent: {self.sport.name}, Opportunity: {parent.sport.name}.")
        if not parent.is_default: 
            raise ValueError(f"Parent must be from default sportsbook.")
        
        self.parent = parent
        self.save()

    def remove_parent(self) -> None: 
        self.parent = None
        self.save()
