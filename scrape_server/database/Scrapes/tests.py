from decimal import Decimal
from django.test import TestCase
import pytz
from .dataclass_models import EventModel, OddModel
from datetime import datetime, timedelta
from .scripts import update_events, update_odds
from ..models import (Event, Opportunity, Sport, Sportsbook, 
                      SportType, ParentOpportunity, Odd, ArbitrageBet, EventLink, OddLink)
from .scrape_service import scrape_sport

class ScrapeTest(TestCase):
    def setUp(self):
        self.sport_type = SportType.objects.create(name="WL")
        self.sport = Sport.objects.create(name="Tennis", selected=True, url="https://example.com", sport_type=self.sport_type)
        self.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True)
        self.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        self.event_models1 = [
            EventModel(1, datetime.now(pytz.utc), 'Roger Federer', 'Rafael Nadal'),
            EventModel(2, datetime.now(pytz.utc), 'Novak Djokovic', 'Andy Murray'),
            EventModel(3, datetime.now(pytz.utc), 'Alexander Zverev', 'Dominic Thiem'),
        ]
        self.event_models2 = [
            EventModel(1, datetime.now(pytz.utc), 'Federer R.', 'Nadal R.'),
            EventModel(2, datetime.now(pytz.utc), 'Djokovic N.', 'Murray A.'),
            EventModel(3, datetime.now(pytz.utc), 'Lukas Lacko', 'Dominik Hrbaty')
        ]

        self.opportunity11 = Opportunity.objects.create(sportsbook= self.sportsbook1, opp_description='Vyhrá *1*', tip_type='tp1', opp_number='12', market_id='21', bet_order=3, sport=self.sport)
        self.opportunity12 = Opportunity.objects.create(sportsbook= self.sportsbook1, opp_description='Vyhrá *2*', tip_type='tp2', opp_number='11', market_id='12', bet_order=5, sport=self.sport)
        
        self.opportunity21 = Opportunity.objects.create(sportsbook= self.sportsbook2, opp_description='Vyhrá *1*', tip_type='tp1', opp_number='32', market_id='13', bet_order=4, sport=self.sport)
        self.opportunity22 = Opportunity.objects.create(sportsbook= self.sportsbook2, opp_description='Vyhrá *2*', tip_type='tp2', opp_number='42', market_id='31', bet_order=1, sport=self.sport)
        self.parent1 = ParentOpportunity.objects.create(description = self.opportunity11.opp_description, sport=self.opportunity11.sport)
        self.parent2 = ParentOpportunity.objects.create(description = self.opportunity12.opp_description, sport=self.opportunity12.sport)
        self.parent1.link_with(self.parent2)
        self.parent1.add_child(self.opportunity21)
        self.parent2.add_child(self.opportunity22)

        self.odd_models1 = [
            OddModel(bet_id=1, odd=2, event_id=1, market_id='21', opp_description='Vyhrá *1*', tip_type='tp1', opp_number='12', bet_order=3),
            OddModel(bet_id=2, odd=1.9, event_id=1, market_id='12', opp_description='Vyhrá *2*', tip_type='tp2', opp_number='11', bet_order=5),
            OddModel(bet_id=3, odd=2.1, event_id=2, market_id='21', opp_description='Vyhrá *1*', tip_type='tp1', opp_number='12', bet_order=3),
            OddModel(bet_id=4, odd=1.7, event_id=2, market_id='12', opp_description='Vyhrá *2*', tip_type='tp2', opp_number='11', bet_order=5),
            OddModel(bet_id=5, odd=2.3, event_id=3, market_id='12', opp_description='Vyhrá *2*', tip_type='tp2', opp_number='11', bet_order=5),
        ]
        self.odd_models2 = [
            OddModel(bet_id=1, odd=2, event_id=1, market_id='13', opp_description='Vyhrá *1*', tip_type='tp1', opp_number='32', bet_order=4),
            OddModel(bet_id=2, odd=1.8, event_id=1, market_id='31', opp_description='Vyhrá *2*', tip_type='tp2', opp_number='42', bet_order=1),
            OddModel(bet_id=3, odd=2.1, event_id=2, market_id='13', opp_description='Vyhrá *1*', tip_type='tp1', opp_number='32', bet_order=4),
            OddModel(bet_id=4, odd=2.3, event_id=3, market_id='13', opp_description='Vyhrá *1*', tip_type='tp1', opp_number='32', bet_order=4),
            OddModel(bet_id=5, odd=1.8, event_id=3, market_id='3441', opp_description='Unnknown opportunity', tip_type='tp2', opp_number='42', bet_order=125),
            OddModel(bet_id=6, odd=2, event_id=7, market_id='3441', opp_description='Unnknown opportunity', tip_type='tp2', opp_number='42', bet_order=125),
        ]

    def test_update_events(self):
        first_batch = self.event_models1
        update_events(first_batch, self.sport.pk, self.sportsbook1.pk)
        self.assertEqual(Event.objects.count(), 3)
        increment = timedelta(hours=2)
        second_batch = self.event_models1[1:]
        new_datetime = datetime.now(pytz.utc)+increment
        second_batch[0] = EventModel(2, new_datetime, 'Novak Djokovic', 'Andy Murray')
        update_events(second_batch, self.sport.pk, self.sportsbook1.pk)
        self.assertEqual(Event.objects.count(), 2)
        changed_event = Event.objects.filter(event_id=second_batch[0].event_id).first()
        assert changed_event.date_time == new_datetime

    def test_update_odds(self): 
        self.run_updates()
        self.assertEqual(Opportunity.objects.count(), 5)
        self.assertEqual(Odd.objects.count(), 9)
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        assert event.odds.count() == 2

        odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, bet_id=1).first()
        odd_to_update.odd = 4
        update_odds([], [odd_to_update], Odd.objects.filter(sportsbook=self.sportsbook1, bet_id=2).all(), self.sport.pk, self.sportsbook1.pk)
        odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, bet_id=1).first()
        self.assertEqual(Odd.objects.count(), 8)
        self.assertEqual(odd_to_update.odd, 4)
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        assert event.odds.count() == 1
    
    def test_chage_of_event_links(self):
        self.run_updates()
        scrape_sport(self.sport.pk, self.sport.name, None, None)
        self.assertEqual(EventLink.objects.count(), 2)
        event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        assert event1.first_event_links.count() + event1.second_event_links.count() == 1
        assert event2.first_event_links.count() + event2.second_event_links.count() == 1
        for link in EventLink.objects.all(): 
            if link.first_event == event1: 
                assert link.second_event == event2
        self.event_models1.append(
            EventModel(4, self.event_models1[0].date_time, 'Federer R.', 'Nadal R.'),
        )
        print("Next update.")
        update_events(self.event_models1, self.sport.pk, self.sportsbook1.pk)
        scrape_sport(self.sport.pk, self.sport.name, None, None)
        self.assertEqual(EventLink.objects.count(), 2)
        event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=4).first()
        event2 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        assert event1.first_event_links.count() + event1.second_event_links.count() == 1
        assert event2.first_event_links.count() + event2.second_event_links.count() == 0
        assert event3.first_event_links.count() + event3.second_event_links.count() == 1
        for link in EventLink.objects.all(): 
            if link.first_event == event1: 
                assert link.second_event == event3
        
        
    def test_flow(self): 
        pass
        # self.run_updates()
        # scrape_sport(self.sport.pk, self.sport.name, None, None)
        # self.assertEqual(EventLink.objects.count(), 2)
        # self.assertEqual(OddLink.objects.count(), 3)
        # self.assertEqual(ArbitrageBet.objects.count(), 0)

        # odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook2, bet_id=2).first()
        # odd_to_update.odd = 3
        # update_odds([], [odd_to_update], [], self.sport.pk, self.sportsbook2.pk)
        # scrape_sport(self.sport.pk, self.sport.name, None, None)
        # self.assertEqual(ArbitrageBet.objects.count(), 1)
        # arb_bet = ArbitrageBet.objects.first()
        # details = arb_bet.details.all()
        # self.assertEqual(arb_bet.profit, Decimal('0.20'))
        # self.assertEqual(len(details), 2)
        # self.assertEqual(details[0].amount, Decimal('0.60'))
        # self.assertEqual(details[1].amount, Decimal('0.40'))
        # self.assertEqual(details[0].opportunity_name, 'Vyhrá Roger Federer')
        # self.assertEqual(details[1].opportunity_name, 'Vyhrá Nadal R.')
        # odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook2, bet_id=2).first()
        # odd_to_update.odd = 102/49
        # update_odds([], [odd_to_update], [], self.sport.pk, self.sportsbook2.pk)
        # scrape_sport(self.sport.pk, self.sport.name, None, None)
        # self.assertEqual(ArbitrageBet.objects.count(), 1)
        # arb_bet = ArbitrageBet.objects.first()
        # self.assertEqual(arb_bet.profit, Decimal('0.0196'))
        # odd_to_update.odd = 1.5
        # update_odds([], [odd_to_update], [], self.sport.pk, self.sportsbook2.pk)
        # scrape_sport(self.sport.pk, self.sport.name, None, None)
        # self.assertEqual(ArbitrageBet.objects.count(), 0)

    def run_updates(self): 
        update_events(self.event_models1, self.sport.pk, self.sportsbook1.pk)
        update_events(self.event_models2, self.sport.pk, self.sportsbook2.pk)
        update_odds(self.odd_models1, [], [], self.sport.pk, self.sportsbook1.pk)
        update_odds(self.odd_models2, [], [], self.sport.pk, self.sportsbook2.pk)