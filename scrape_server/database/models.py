from __future__ import annotations
from django.db import models

class Sport(models.Model):
    name = models.CharField(max_length=20, unique=True)
    url = models.CharField(max_length=20)
    selected = models.BooleanField(default=False)

class Sportsbook(models.Model):
    name = models.CharField(max_length=30, unique=True)
    is_default = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    tenis_url = models.CharField(max_length=50)
    darts_url = models.CharField(max_length=50)
    cricket_url = models.CharField(max_length=50)
    baseball_url = models.CharField(max_length=50)
    table_tennis_url = models.CharField(max_length=50)
    snooker_url = models.CharField(max_length=50)
    volleyball_url = models.CharField(max_length=50)
    football_url = models.CharField(max_length=50)
    hockey_url = models.CharField(max_length=50)

class Event(models.Model):
    event_id = models.IntegerField()
    time = models.CharField(max_length=30)
    home = models.CharField(max_length=50)
    away = models.CharField(max_length=50)
    is_default = models.BooleanField(default=False)
    selected = models.BooleanField(default=False)
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', default=None)

    def add_parent(self, parent: Event) -> None:
        if parent.sport != self.sport: 
            raise ValueError(f"Sport mismatch. Parent: {self.sport.name}, Event: {parent.sport.name}.")
        if not parent.is_default: 
            raise ValueError(f"Parent must be from default sportsbook.")
        self.parent = parent
        self.save()

class Odd(models.Model):
    odd_id = models.IntegerField()
    code= models.IntegerField()
    odd = models.DecimalField(max_digits=6, decimal_places=2)
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
        self.save()

    def can_be_linked(self, odd: Odd) -> bool:
        return self.opportunity.parent == odd.opportunity

class Opportunity(models.Model):
    description = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)
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

    @property
    def has_parent(self) -> bool:
        return self.parent is not None
