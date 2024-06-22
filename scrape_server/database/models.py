from __future__ import annotations
from django.db import models
from datetime import timedelta, datetime
import pytz
from Utils import odds_to_implied_pb, get_profit, stake_for_arbitrage_bet

class Sport(models.Model):
    name = models.CharField(max_length=20, unique=True)
    selected = models.BooleanField(default=False)
    url = models.CharField(max_length=20)
    sport_type = models.ForeignKey('SportType', on_delete=models.CASCADE)

class SportType(models.Model):
    name = models.CharField(max_length=20, unique=True)

class Sportsbook(models.Model):
    name = models.CharField(max_length=30, unique=True)
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
    
class EventLink(models.Model):
    first_event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='first_event_links')
    second_event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='second_event_links')
    score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    sport_id = models.IntegerField(default=None)

    def change_link(self, new_event: Event, position: int, best_score: float) -> None:
        if position == 1:
            self.first_event = new_event
        elif position == 2:
            self.second_event = new_event   
        else:   
            raise ValueError(f"Position must be 1 or 2. Now it is {position}.")   
        self.score = best_score
        self.save()

    def is_potential_link(self, best_event: Event, event_to_be_linked: Event) -> bool: 
        return self.second_event == best_event and self.first_event.sportsbook == event_to_be_linked.sportsbook

class Event(models.Model):
    event_id = models.IntegerField()
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    date_time = models.DateTimeField()
    first_name = models.CharField(max_length=50)
    second_name = models.CharField(max_length=50)
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)

    def get_existing_link(self, sportsbook: Sportsbook) -> tuple[int, EventLink]:
        if self.first_event_links.filter(second_event__sportsbook=sportsbook).count() > 0: 
            return (2, self.first_event_links.filter(second_event__sportsbook=sportsbook).first())
        if self.second_event_links.filter(first_event__sportsbook=sportsbook).count() > 0: 
            return (1, self.second_event_links.filter(first_event__sportsbook=sportsbook).first())
        return None, None
    
    def get_targets(self) -> list[Sportsbook]: 
        used_sportsbook_ids = set()
        used_sportsbook_ids.add(self.sportsbook.pk)
        for link in self.first_event_links.all(): 
            used_sportsbook_ids.add(link.second_event.sportsbook.pk)
        for link in self.second_event_links.all(): 
            used_sportsbook_ids.add(link.first_event.sportsbook.pk)    
        return Sportsbook.objects.filter(selected=True).exclude(id__in=used_sportsbook_ids).all()    
    
    def is_in_time_window(self, event: Event) -> bool: 
        increment = timedelta(hours=1)
        return self.date_time <= event.date_time + increment and event.date_time >= event.date_time - increment
    
    @property
    def number_of_links(self) -> int:
        return self.first_event_links.count() + self.second_event_links.count()

class ArbitrageBet(models.Model):
    updated = models.DateTimeField(auto_now_add=True)
    first_odd_id = models.IntegerField()
    second_odd_id = models.IntegerField()
    sport_id = models.IntegerField()
    sport_name = models.CharField(max_length=20)
    profit = models.DecimalField(max_digits=6, decimal_places=4)

    def update_instance(self, oddlink: OddLink): 
        self.updated = datetime.now(pytz.utc)
        self.profit = get_profit(odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))

class ArbitrageBetDetail(models.Model):
    arbitrage_bet = models.ForeignKey(ArbitrageBet, on_delete=models.CASCADE, related_name='details')
    player_name = models.CharField(max_length=50)
    sportsbook_name = models.CharField(max_length=30)
    opportunity_name = models.CharField(max_length=200)
    odd = models.DecimalField(max_digits=6, decimal_places=2)
    amount = models.DecimalField(max_digits=6, decimal_places=4)

    def update_instance(self, odd: Odd, oddlink: OddLink): 
        self.odd = odd.odd
        self.amount = stake_for_arbitrage_bet(odds_to_implied_pb([odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))

class Odd(models.Model):
    bet_id = models.IntegerField()
    tip_type = models.CharField(max_length=3)
    odd = models.DecimalField(max_digits=6, decimal_places=2)
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='odds')
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE)

    def is_linked_to_event(self, event: Event) -> bool:
        first_links_count = self.first_odd_links.filter(second_odd__event=event).count()
        if first_links_count > 0: return True
        second_links_count = self.second_odd_links.filter(first_odd__event=event).count()
        return second_links_count > 0

    def can_be_linked(self, odd: Odd) -> bool:
        return self.opportunity.is_linked_to(odd.opportunity)

class OddLink(models.Model):
    first_odd = models.ForeignKey('Odd', on_delete=models.CASCADE, related_name='first_odd_links')
    second_odd = models.ForeignKey('Odd', on_delete=models.CASCADE, related_name='second_odd_links')
    sport_id = models.IntegerField(default=None)

class ParentOpportunity(models.Model):
    description = models.CharField(max_length=200)
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)
    linked_opportunity = models.OneToOneField(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='linked_to',
        default=None, 
    )

    @classmethod
    def create_parent_opportunities(cls, opportunities: list[Opportunity]) -> list[ParentOpportunity]: 
        parent_opportunitites = [cls.objects.create(description = opportunity.opp_description, sport= opportunity.sport) for opportunity in opportunities]
        return parent_opportunitites

    def link_with(self, other_opportunity: ParentOpportunity) -> None:
        if self.pk is None or other_opportunity.pk is None:
            raise ValueError("Both opportunities must be saved before linking.")
        if self == other_opportunity:
            raise ValueError("Cannot link same parent opportunity.")
        
        self.linked_opportunity = other_opportunity
        other_opportunity.linked_opportunity = self
        self.save()
        other_opportunity.save()
    
    def is_linked_to(self, other_opportunity: ParentOpportunity) -> bool:
        return self.linked_opportunity == other_opportunity and other_opportunity.linked_opportunity == self

    def add_child(self, opportunity: Opportunity) -> None:
        if opportunity.sport != self.sport: 
            raise ValueError(f"Sport mismatch. Parent: {self.sport.name}, Opportunity: {opportunity.sport.name}.")
        opportunity.parent = self
        opportunity.save()

class Opportunity(models.Model):
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    opp_description = models.CharField(max_length=200)
    tip_type = models.CharField(max_length=3)
    opp_number = models.CharField(max_length=10)
    market_id = models.CharField(max_length=10)
    bet_order = models.IntegerField()
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)
    parent = models.ForeignKey('ParentOpportunity', on_delete=models.SET_NULL, null=True, blank=True, default=None, related_name='children')

    class Meta:
        indexes = [
            models.Index(fields=['sportsbook_id', 'sport_id', 'tip_type', 'opp_number', 'market_id', 'bet_order']),
        ]

    def is_linked_to(self, other_opportunity: Opportunity) -> bool:
        if self.parent is None or other_opportunity.parent is None: return False
        return self.parent.is_linked_to(other_opportunity.parent)

    def remove_parent(self): 
        self.parent = None
        self.save()

    @property
    def has_parent(self) -> bool:
        return self.parent is not None
