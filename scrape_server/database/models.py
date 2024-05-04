from django.db import models

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

class EventToBeLinked(models.Model):
    sport_id = models.IntegerField()
    event = models.ForeignKey('Event', on_delete=models.CASCADE)
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    class Meta:
        indexes = [
            models.Index(fields=['sport_id']),
        ]
        
class Event(models.Model):
    event_id = models.IntegerField()
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    date_time = models.DateTimeField()
    first_name = models.CharField(max_length=50)
    second_name = models.CharField(max_length=50)
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)

    def delete(self, *args, **kwargs):
        for odd in self.odds.all():
            odd.delete()

        super().delete(*args, **kwargs)

class ArbitrageBet(models.Model):
    updated = models.DateTimeField(auto_now_add=True)
    first_odd_id = models.IntegerField()
    second_odd_id = models.IntegerField()
    sport_id = models.IntegerField()
    sport_name = models.CharField(max_length=20)
    profit = models.DecimalField(max_digits=6, decimal_places=2)
    
class ArbitrageBetDetail(models.Model):
    arbitrage_bet = models.ForeignKey(ArbitrageBet, on_delete=models.CASCADE, related_name='details')
    player_name = models.CharField(max_length=50)
    sportsbook_name = models.CharField(max_length=30)
    opportunity_name = models.CharField(max_length=50)
    odd = models.DecimalField(max_digits=6, decimal_places=2)
    amount = models.DecimalField(max_digits=6, decimal_places=2)

class Odd(models.Model):
    bet_id = models.IntegerField()
    tip_type = models.CharField(max_length=3)
    odd = models.DecimalField(max_digits=6, decimal_places=2)
    event = models.ForeignKey('Event', on_delete=models.DO_NOTHING, related_name='odds')
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE)

    def delete(self, *args, **kwargs):
        for odd_link in self.first_odd_links.all():
            odd_link.delete()
        for odd_link in self.second_odd_links.all():
            odd_link.delete()

        super().delete(*args, **kwargs)

class OddLink(models.Model):
    first_odd = models.ForeignKey('Odd', on_delete=models.DO_NOTHING, related_name='first_odd_links')
    second_odd = models.ForeignKey('Odd', on_delete=models.DO_NOTHING, related_name='second_odd_links')
    sport_id = models.IntegerField(default=None)
    opportunity_link = models.ForeignKey('OpportunityLink', on_delete=models.CASCADE, default=None)
    
    def delete(self, *args, **kwargs):
        if self.first_odd:
            OddToBeLinked.objects.create(odd=self.second_odd, sport_id=self.sport_id, opportunity_link=self.opportunity_link, event=self.second_odd.event)
        if self.second_odd:
            OddToBeLinked.objects.create(odd=self.first_odd, sport_id=self.sport_id, opportunity_link=self.opportunity_link, event=self.first_odd.event)
        
        super().delete(*args, **kwargs)

class OddToBeLinked(models.Model):
    odd = models.ForeignKey('Odd', on_delete=models.CASCADE)
    sport_id = models.IntegerField()
    opportunity_link = models.ForeignKey('OpportunityLink', on_delete=models.CASCADE, default=None)
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='oddstobelinked', default=None)

    class Meta:
        indexes = [
            models.Index(fields=['sport_id']),
        ]

class Opportunity(models.Model):
    sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE)
    opp_description = models.CharField(max_length=200)
    tip_type = models.CharField(max_length=3)
    opp_number = models.CharField(max_length=10)
    market_id = models.CharField(max_length=10)
    bet_order = models.IntegerField()
    sport = models.ForeignKey('Sport', on_delete=models.CASCADE)  
    class Meta:
        indexes = [
            models.Index(fields=['sportsbook_id', 'sport_id', 'tip_type', 'opp_number', 'market_id', 'bet_order']),
        ]

class OpportunityLink(models.Model):
    first_opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE, related_name='first_opportunity_links')
    second_opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE, related_name='second_opportunity_links')

class OpportunityToBeLinked(models.Model):
    opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE)
    target_sportsbook = models.ForeignKey('Sportsbook', on_delete=models.CASCADE, related_name='opportunities_to_be_linked')
        