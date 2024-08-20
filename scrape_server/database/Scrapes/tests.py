from django.test import TestCase
from .dataclass_models import EventModel, MatchResponse, OddModel
from .scripts import (update_events, update_odds, update_selected_events, 
                      get_selected_events, clear_unused_events, link_all_events,
                      link_odds)
from ..models import (Event, Opportunity, Sport, Sportsbook, Odd)

class ScrapeTest(TestCase):
    def setUp(self):
        self.sport = Sport.objects.create(name="Tennis", selected=True, url="https://example.com")
        self.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        self.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        self.event_models1 = [
            EventModel(None, 1, "", 'Roger Federer', 'Rafael Nadal', self.sportsbook1.is_default, False, self.sportsbook1.pk, self.sport.pk, [], 5),
            EventModel(None, 2, "", 'Novak Djokovic', 'Andy Murray', self.sportsbook1.is_default, False, self.sportsbook1.pk, self.sport.pk, [], 5),
            EventModel(None, 3, "", 'Alexander Zverev', 'Dominic Thiem', self.sportsbook1.is_default, False, self.sportsbook1.pk, self.sport.pk, [], 5),
        ]
        self.event_models2 = [
            EventModel(None, 1, "", 'Federer R.', 'Nadal R.', self.sportsbook2.is_default, False, self.sportsbook2.pk, self.sport.pk, [], 5),
            EventModel(None, 2, "", 'Djokovic N.', 'Murray A.', self.sportsbook2.is_default, False, self.sportsbook2.pk, self.sport.pk, [], 5),
            EventModel(None, 3, "", 'Lukas Lacko', 'Dominik Hrbaty', self.sportsbook2.is_default, False, self.sportsbook2.pk, self.sport.pk, [], 5)
        ]

        self.opportunity11 = Opportunity.objects.create(sportsbook= self.sportsbook1, description='Vyhrá *1*', market_id='21', sport=self.sport, is_default=self.sportsbook1.is_default, prefered=False)
        self.opportunity12 = Opportunity.objects.create(sportsbook= self.sportsbook1, description='Vyhrá *2*', market_id='12', sport=self.sport, is_default=self.sportsbook1.is_default, prefered=False)
        
        self.opportunity21 = Opportunity.objects.create(sportsbook= self.sportsbook2, description='Vyhrá *1*', market_id='13', sport=self.sport, is_default=self.sportsbook2.is_default, prefered=False)
        self.opportunity22 = Opportunity.objects.create(sportsbook= self.sportsbook2, description='Vyhrá *2*', market_id='31', sport=self.sport, is_default=self.sportsbook2.is_default, prefered=False)

        self.opportunity21.add_parent(self.opportunity11)
        
        self.odd_models1 = [
            OddModel(id=None, odd_id=1, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=2, event_id=1, market_id='21', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=2, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=1.9, event_id=1, market_id='12', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *2*'),
            OddModel(id=None, odd_id=3, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=2.1, event_id=2, market_id='21', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=4, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=1.7, event_id=2, market_id='12', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *2*'),
            OddModel(id=None, odd_id=5, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='12', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *2*'),
        ]
        self.odd_models2 = [
            OddModel(id=None, odd_id=1, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=1, market_id='13', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=2, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=1, market_id='31', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *2*'),
            OddModel(id=None, odd_id=3, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2.1, event_id=2, market_id='13', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=4, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='13', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=5, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=3, market_id='3441', sportsbook_id=self.sportsbook2.pk, description='Unnknown opportunity'),
            OddModel(id=None, odd_id=6, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=7, market_id='3441', sportsbook_id=self.sportsbook2.pk, description='Unnknown opportunity'),
        ]

    def test_update_events(self):
        first_batch = self.event_models1
        update_events(first_batch, self.sportsbook1)
        self.assertEqual(Event.objects.count(), 3)
        second_batch = self.event_models1[1:]
        second_batch[0] = EventModel(None, 2, "new_time", 'Novak Djokovic', 'Andy Murray', False, False, 1, 1, [], 5)
        update_events(second_batch, self.sportsbook1)
        self.assertEqual(Event.objects.count(), 2)
        changed_event = Event.objects.filter(event_id=second_batch[0].event_id).first()
        assert changed_event.time == "new_time"
        assert changed_event.is_default
        all_events = Event.objects.all()
        event = all_events[0]
        event.time = "new_time1"
        update_selected_events([event], [all_events[1]])
        self.assertEqual(Event.objects.count(), 1)
        assert Event.objects.first().time == "new_time1"

    def test_update_odds(self): 
        self.run_updates()
        self.assertEqual(Opportunity.objects.count(), 5)
        self.assertEqual(Odd.objects.count(), 9)
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        assert event.odds.count() == 2

        odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd_to_update.odd = 4
        update_odds([], [odd_to_update], self.sportsbook1)
        Event.objects.filter(sportsbook=self.sportsbook1, event_id=3).delete()
        odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        self.assertEqual(Odd.objects.count(), 8)
        self.assertEqual(odd_to_update.odd, 4)
        assert Odd.objects.filter(sportsbook=self.sportsbook1, event_id=3).count() == 0
    
    def test_get_selected_events(self): 
        self.run_updates()
        event = Event.objects.filter(sportsbook=self.sportsbook1).first()
        event.selected = True
        event.save()
        result, sport_ids = get_selected_events(self.sportsbook1)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(sport_ids), 1)
        child_event = Event.objects.filter(sportsbook=self.sportsbook2).first()
        child_event.add_parent(event)
        child_event.save()
        result, sport_ids = get_selected_events(self.sportsbook2)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(sport_ids), 1)

    def test_clear_unused_events(self): 
        self.run_updates()
        self.sportsbook2.selected = False
        self.sportsbook2.save()
        clear_unused_events()
        self.assertEqual(Event.objects.count(), 3)
        
    def test_chage_of_parents(self):
        self.event_models2.append(
            EventModel(None, 4, "", 'Roger Federe', 'Rafael Nada', False, False, self.sportsbook2.pk, self.sport.pk, [], 5),
        )
        self.run_updates()
        link_all_events()
        event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=4).first()
        self.assertEqual(event2.parent, None)
        self.assertEqual(event3.parent, event1)
        self.event_models2.append(
            EventModel(None, 5, "", 'Roger Federer', 'Rafael Nadal', False, False, self.sportsbook2.pk, self.sport.pk, [], 5),
        )
        update_events(self.event_models2, self.sportsbook2)
        link_all_events()
        event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=4).first()
        event4 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=5).first()
        self.assertEqual(event2.parent, None)
        self.assertEqual(event3.parent, None)
        self.assertEqual(event4.parent, event1)

    def test_link_odds(self): 
        self.run_updates()
        link_all_events()
        link_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1).first()
        event.selected = True
        event.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1).first()
        odd.selected = True
        odd.save()
        sportsbook = Sportsbook.objects.get(is_default=True, selected=True)
        events, _ = get_selected_events(sportsbook)
        response = MatchResponse.dataclass_from_models(events, Sportsbook.objects.filter(selected=True).order_by('-is_default').all())
        self.assertEqual(len(response.matches), 1)
        self.assertEqual(len(response.sportsbook_ids), 2)
        match = response.matches[0]
        self.assertEqual(match.match_id, event.pk)
        self.assertEqual(len(match.opportunities), 1)
        opportunity = match.opportunities[0]
        self.assertEqual(len(opportunity.odds), 2)
        self.assertEqual(opportunity.odds[0].odd_id, 1)
        self.assertEqual(opportunity.odds[1].odd_id, 1)

    def run_updates(self): 
        update_events(self.event_models1, self.sportsbook1)
        update_events(self.event_models2, self.sportsbook2)
        update_odds(self.odd_models1, [], self.sportsbook1)
        update_odds(self.odd_models2, [], self.sportsbook2)