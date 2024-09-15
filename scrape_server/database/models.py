from __future__ import annotations
from django.db import models
from fuzzywuzzy import fuzz

class Sport(models.Model):
    name = models.CharField(max_length=20, unique=True)
    url = models.CharField(max_length=20)
    selected = models.BooleanField(default=False)

class Sportsbook(models.Model):
    name = models.CharField(max_length=30, unique=True)
    is_default = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    football_url = models.CharField(max_length=20)
    hockey_url = models.CharField(max_length=20)
    tenis_url = models.CharField(max_length=20)
    basketball_url = models.CharField(max_length=20)
    handball_url = models.CharField(max_length=20)
    volleyball_url = models.CharField(max_length=20)
    table_tennis_url = models.CharField(max_length=20)
    box_url = models.CharField(max_length=20)

class SportsbookMarket(models.Model):
    value = models.CharField(max_length=50)
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE, related_name='markets')

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
    
class Odd(models.Model):
    odd_id = models.BigIntegerField()
    code= models.IntegerField()
    movement= models.IntegerField(default=0)
    odd = models.DecimalField(max_digits=10, decimal_places=2)
    is_default = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='odds')
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', default=None)

    def add_parent(self, parent: Odd) -> None:
        if not parent.is_default: 
            raise ValueError(f"Parent must be from default sportsbook.")
        self.parent = parent

    def can_be_linked(self, odd: Odd) -> bool:
        return self.opportunity.parent == odd.opportunity
    
    def should_be_updated(self) -> bool:
        return self.movement != 0 or self.locked
    
    def to_decimal(self):
        if self.odd > 0:
            decimal_odds = (self.odd / 100) + 1
        else:
            decimal_odds = (100 / abs(self.odd)) + 1
        return round(decimal_odds, 3)
    
    def ev(self, parent_odds: float) -> float: 
        impl_prob = 1/parent_odds
        ev = (impl_prob * (float(self.odd)-1)) - (1 - impl_prob)
        return round(100*ev, 2)
    
    def stake(self, parent_odds: float) -> float: 
        odds_float = float(self.odd)
        if odds_float==1: return 0
        impl_prob = 1/parent_odds
        kelly = impl_prob - (1 - impl_prob)/(odds_float-1)
        return round(kelly, 2)
    
class Opportunity(models.Model):
    description = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)
    prefered = models.BooleanField(default=False)
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', default=None)
    market_id = models.CharField(max_length=20)
    
    class Meta:
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

    def remove_parent(self): 
        self.parent = None
        self.save()
