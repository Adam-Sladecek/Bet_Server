import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'scrape_server.settings'
django.setup()

from django.test import TestCase
import json 
import queue
import threading
from unittest.mock import patch, MagicMock

from common_test_methods import reset_database
from database.enums import Command, DataType
from database.models import Sportsbook, Sport, Event, Opportunity, Odd
from database.Scrapes.main import scrape_fn
from database.Scrapes.dataclass_models import EventModel, OddModel
from database.Scrapes.helpers import EventHelper, OddHelper, ScrapeHelper
"""
    This class tests overall scraping flow contained in scrape.py and scrape_service.py.
"""
class TestScrapeProcess(TestCase):
    @patch('database.models.Sport.objects.filter')
    @patch('database.models.Sportsbook.objects.filter')
    @patch('database.Scrapes.scrape_service.ScrapeHelper.link_events_and_odds')
    @patch('database.Scrapes.scrape_service.ScrapeHelper.send_updated_events')
    @patch('database.Scrapes.scrape_service.TipsportScraper')
    @patch('database.Scrapes.scrape_service.NikeScraper')
    def test_scrape_fn_with_sportsbook_data(self, mock_nike_scraper, mock_tipsport_scraper, mock_send_updated_events, 
                                            mock_link_events_and_odds, mock_sportsbook_filter, mock_sport_filter):
        # Arange
        mock_sportsbook_nike = MagicMock()
        mock_sportsbook_nike.pk = 1
        mock_sportsbook_nike.name = 'Nike'

        mock_sportsbook_tipsport = MagicMock()
        mock_sportsbook_tipsport.pk = 2
        mock_sportsbook_tipsport.name = 'Tipsport'

        mock_sport_filter.return_value.all.return_value = [MagicMock(name='Sport 1')]
        mock_sportsbook_filter.return_value.all.return_value = [mock_sportsbook_nike, mock_sportsbook_tipsport]

        # NOTE: this is needed in order for 'with' block to work properly in ScrapeService.get_sportsbook_data test
        mock_nike_scraper.return_value.__enter__.return_value = mock_nike_scraper.return_value
        mock_nike_scraper.return_value.__exit__.return_value = False
        mock_tipsport_scraper.return_value.__enter__.return_value = mock_tipsport_scraper.return_value
        mock_tipsport_scraper.return_value.__exit__.return_value = False

        mock_nike_scraper.return_value.get_data = MagicMock()
        mock_tipsport_scraper.return_value.get_data = MagicMock()
        mock_nike_scraper.return_value.import_all_data = MagicMock()
        mock_tipsport_scraper.return_value.import_all_data = MagicMock()

        event = threading.Event()
        send_all_event = threading.Event()
        import_queue = queue.Queue()

        # Act
        scrape_thread = threading.Thread(target=scrape_fn, args=(event, import_queue, send_all_event))
        scrape_thread.start()
        threading.Event().wait(2)
        import_queue.put(Command.IMPORT)
        threading.Event().wait(4)
        event.set()
        scrape_thread.join()

        # Assert
        mock_nike_scraper.assert_called_with(mock_sportsbook_nike, [mock_sport_filter.return_value.all.return_value[0]])
        mock_tipsport_scraper.assert_called_with(mock_sportsbook_tipsport, [mock_sport_filter.return_value.all.return_value[0]])

        mock_nike_scraper.return_value.get_data.assert_called()
        mock_tipsport_scraper.return_value.get_data.assert_called()
        self.assertEqual(mock_nike_scraper.return_value.import_all_data.call_count, 1)
        self.assertEqual(mock_tipsport_scraper.return_value.import_all_data.call_count, 1)

        mock_link_events_and_odds.assert_called() 
        mock_send_updated_events.assert_called() 
        self.assertTrue(import_queue.empty())

class TestEventHepler(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Tennis", selected=True, url="https://example.com")
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        cls.event_helper = EventHelper(cls.sportsbook)
        cls.event_helper2 = EventHelper(cls.sportsbook2)
        cls.event_models = [
            EventModel(None, 1, 0, "", 'Roger Federer', 'Rafael Nadal', cls.sportsbook.is_default, True, cls.sportsbook.pk, cls.sport.pk, [], 0),
            EventModel(None, 2, 0, "", 'Novak Djokovic', 'Andy Murray', cls.sportsbook.is_default, False, cls.sportsbook.pk, cls.sport.pk, [], 0),
            EventModel(None, 3, 0, "", 'Alexander Zverev', 'Dominic Thiem', cls.sportsbook.is_default, True, cls.sportsbook.pk, cls.sport.pk, [], 0),
        ]
        cls.event_models2 = [
            EventModel(None, 1, 0, "", 'Federer R.', 'Nadal R.', cls.sportsbook2.is_default, True, cls.sportsbook2.pk, cls.sport.pk, [], 0),
            EventModel(None, 2, 0, "", 'Djokovic N.', 'Murray A.', cls.sportsbook2.is_default, False, cls.sportsbook2.pk, cls.sport.pk, [], 0),
            EventModel(None, 3, 0, "", 'Lukas Lacko', 'Dominik Hrbaty', cls.sportsbook2.is_default, True, cls.sportsbook2.pk, cls.sport.pk, [], 0)
        ]

    def test_update_and_delete_events(self):
        # update_events
        first_batch = self.event_models
        self.event_helper.update_events(first_batch)
        self.assertEqual(Event.objects.count(), 3)
        second_batch = self.event_models[1:]
        second_batch[0] = EventModel(None, 2, 0, "new_time", 'Novak Djokovic', 'Andy Murray', True, False, 1, 1, [], 0)
        self.event_helper.update_events(second_batch)
        self.assertEqual(Event.objects.count(), 2)
        changed_event = Event.objects.filter(event_id=second_batch[0].event_id).first()
        assert changed_event.time == "new_time"
        assert changed_event.is_default

        # update_selected_events
        all_events = Event.objects.all()
        event = all_events[0]
        event.time = "new_time1"
        self.event_helper.update_selected_events([event], [all_events[1]])
        self.assertEqual(Event.objects.count(), 1)
        assert Event.objects.first().time == "new_time1"

        # delete_settled_events
        event_ids = [1,2, event.event_id, 3, 4]
        self.event_helper.delete_settled_events(event_ids)
        self.assertEqual(Event.objects.count(), 0)

    def test_get_selected_events(self):
        # Arrange
        self.event_helper.update_events(self.event_models)
        self.event_helper2.update_events(self.event_models2)
        self.assertEqual(Event.objects.count(), 6)
        first_event = Event.objects.filter(sportsbook=self.sportsbook, event_id=1).first()
        second_event = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        second_event.add_parent(first_event)
        second_event.save()

        # Act 
        default_selected_events, default_sport_ids = self.event_helper.get_selected_events()
        selected_events, sport_ids = self.event_helper2.get_selected_events()

        # Assert 
        sport_ids = set([self.sport.pk])
        self.assertEqual(default_sport_ids, sport_ids)
        self.assertEqual(sport_ids, sport_ids)
        self.assertEqual(default_selected_events, [event for event in Event.objects.filter(sportsbook=self.sportsbook, event_id__in=[1,3]).all()])
        self.assertEqual(selected_events, [event for event in Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).all()])

class TestOddHepler(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Tennis", selected=True, url="https://example.com")
        cls.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        cls.event_helper = EventHelper(cls.sportsbook1)
        cls.event_helper2 = EventHelper(cls.sportsbook2)
        cls.odd_helper = OddHelper(cls.sportsbook1)
        cls.odd_helper2 = OddHelper(cls.sportsbook2)
        cls.event_models1 = [
            EventModel(None, 1, 0, "", 'Roger Federer', 'Rafael Nadal', cls.sportsbook1.is_default, False, cls.sportsbook1.pk, cls.sport.pk, [], 0),
            EventModel(None, 2, 0, "", 'Novak Djokovic', 'Andy Murray', cls.sportsbook1.is_default, False, cls.sportsbook1.pk, cls.sport.pk, [], 0),
            EventModel(None, 3, 0, "", 'Alexander Zverev', 'Dominic Thiem', cls.sportsbook1.is_default, False, cls.sportsbook1.pk, cls.sport.pk, [], 0),
        ]
        cls.event_models2 = [
            EventModel(None, 1, 0, "", 'Federer R.', 'Nadal R.', cls.sportsbook2.is_default, False, cls.sportsbook2.pk, cls.sport.pk, [], 0),
            EventModel(None, 2, 0, "", 'Djokovic N.', 'Murray A.', cls.sportsbook2.is_default, False, cls.sportsbook2.pk, cls.sport.pk, [], 0),
            EventModel(None, 3, 0, "", 'Lukas Lacko', 'Dominik Hrbaty', cls.sportsbook2.is_default, False, cls.sportsbook2.pk, cls.sport.pk, [], 0)
        ]

        cls.opportunity11 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhrá *1*', market_id='21', sport=cls.sport, is_default=cls.sportsbook1.is_default, prefered=False)
        cls.opportunity12 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhrá *2*', market_id='12', sport=cls.sport, is_default=cls.sportsbook1.is_default, prefered=False)
        cls.opportunity21 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhrá *1*', market_id='13', sport=cls.sport, is_default=cls.sportsbook2.is_default, prefered=False)
        cls.opportunity22 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhrá *2*', market_id='31', sport=cls.sport, is_default=cls.sportsbook2.is_default, prefered=False)

        cls.opportunity21.add_parent(cls.opportunity11)
        
        cls.odd_models1 = [
            OddModel(id=None, odd_id=1, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=2, event_id=1, market_id='21', sportsbook_id=cls.sportsbook1.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=2, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=1.9, event_id=1, market_id='12', sportsbook_id=cls.sportsbook1.pk, description='Vyhrá *2*'),
            OddModel(id=None, odd_id=3, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=2.1, event_id=2, market_id='21', sportsbook_id=cls.sportsbook1.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=4, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=1.7, event_id=2, market_id='12', sportsbook_id=cls.sportsbook1.pk, description='Vyhrá *2*'),
            OddModel(id=None, odd_id=5, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='12', sportsbook_id=cls.sportsbook1.pk, description='Vyhrá *2*'),
        ]
        cls.odd_models2 = [
            OddModel(id=None, odd_id=1, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=1, market_id='13', sportsbook_id=cls.sportsbook2.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=2, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=1, market_id='31', sportsbook_id=cls.sportsbook2.pk, description='Vyhrá *2*'),
            OddModel(id=None, odd_id=3, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2.1, event_id=2, market_id='13', sportsbook_id=cls.sportsbook2.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=4, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='13', sportsbook_id=cls.sportsbook2.pk, description='Vyhrá *1*'),
            OddModel(id=None, odd_id=5, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=3, market_id='3441', sportsbook_id=cls.sportsbook2.pk, description='Unnknown opportunity'), # this is here to assert that odd with no matching event opportunity be created
            OddModel(id=None, odd_id=6, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=3, market_id='3441', sportsbook_id=cls.sportsbook2.pk, description='Unnknown opportunity'), # this is here to assert that second odd with no matching opportunity wont be created and that only one new opportunity will be added
            OddModel(id=None, odd_id=7, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=8, market_id='3441', sportsbook_id=cls.sportsbook2.pk, description='Vyhrá *1*'), # this is here to assert that odd with no matching event wont be created
        ]   

    def test_update_odds(self): 
            self.run_updates()
            self.assertEqual(Opportunity.objects.count(), 5)
            self.assertEqual(Odd.objects.count(), 9)
            event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
            assert event.odds.count() == 2
            odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
            odd_to_update.odd = 4
            odd_to_update.locked = True
            odd_to_update.movement = 2
            self.odd_helper.update_odds([], [odd_to_update])
            Event.objects.filter(sportsbook=self.sportsbook1, event_id=3).delete()
            odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
            self.assertEqual(Odd.objects.count(), 8)
            self.assertEqual(odd_to_update.odd, 4)
            self.assertTrue(odd_to_update.locked)
            self.assertEqual(odd_to_update.movement, 2)
            assert Odd.objects.filter(sportsbook=self.sportsbook1, event_id=3).count() == 0

    def test_update_movements(self): 
        # Arange
        self.run_updates()
        odds= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id__in=[1,2,3]).all()
        for odd in odds: 
            odd.movement=1
            odd.save()

        # Act 
        self.odd_helper.update_movements(Event.objects.filter(sportsbook=self.sportsbook1, event_id__in=[1,2]).all())

        # Assert
        odds= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id__in=[1,2,3]).all()
        for odd in odds: 
            self.assertEqual(odd.movement, 0)

    def test_get_existing_odds(self):
        # Arange
        self.event_helper.update_events(self.event_models1)
        self.odd_helper.update_odds(self.odd_models1, [])

        # Act 
        odds_without_code = self.odd_helper.get_existing_odds()
        odds_with_code = self.odd_helper.get_existing_odds(True)

        # Assert
        event_ids = [event.event_id for event in Event.objects.filter(sportsbook=self.sportsbook1).all()]
        self.assertEqual(list(odds_without_code.keys()), event_ids)
        self.assertEqual(list(odds_with_code.keys()), event_ids)
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        self.assertEqual(odds_without_code[1][1], odd)
        self.assertEqual(odds_with_code[1][(1,0)], odd)

    def run_updates(self): 
        self.event_helper.update_events(self.event_models1)
        self.event_helper2.update_events(self.event_models2)
        self.odd_helper.update_odds(self.odd_models1, [])
        self.odd_helper2.update_odds(self.odd_models2, [])        

class TestScrapeHelper(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Tennis", selected=True, url="https://example.com")
        cls.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        cls.event_helper = EventHelper(cls.sportsbook1)
        cls.event_helper2 = EventHelper(cls.sportsbook2)
        cls.odd_helper = OddHelper(cls.sportsbook1)
        cls.odd_helper2 = OddHelper(cls.sportsbook2)
        cls.event_models1 = [
            EventModel(None, 1, 0, "", 'Roger Federer', 'Rafael Nadal', cls.sportsbook1.is_default, False, cls.sportsbook1.pk, cls.sport.pk, [], 0),
            EventModel(None, 2, 0, "", 'Novak Djokovic', 'Andy Murray', cls.sportsbook1.is_default, False, cls.sportsbook1.pk, cls.sport.pk, [], 0),
            EventModel(None, 3, 0, "", 'Alexander Zverev', 'Dominic Thiem', cls.sportsbook1.is_default, False, cls.sportsbook1.pk, cls.sport.pk, [], 0),
        ]
        cls.event_models2 = [
            EventModel(None, 1, 0, "", 'Federer R.', 'Nadal R.', cls.sportsbook2.is_default, False, cls.sportsbook2.pk, cls.sport.pk, [], 0),
            EventModel(None, 2, 0, "", 'Djokovic N.', 'Murray A.', cls.sportsbook2.is_default, False, cls.sportsbook2.pk, cls.sport.pk, [], 0),
            EventModel(None, 3, 0, "", 'Lukas Lacko', 'Dominik Hrbaty', cls.sportsbook2.is_default, False, cls.sportsbook2.pk, cls.sport.pk, [], 0) # this event should not be linked -> no matching default event
        ]

        cls.opportunity11 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhra *1*', market_id='21', sport=cls.sport, is_default=cls.sportsbook1.is_default, prefered=False)
        cls.opportunity12 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhra *2*', market_id='12', sport=cls.sport, is_default=cls.sportsbook1.is_default, prefered=False)
        cls.opportunity21 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhra *1*', market_id='13', sport=cls.sport, is_default=cls.sportsbook2.is_default, prefered=False)
        cls.opportunity22 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhra *2*', market_id='31', sport=cls.sport, is_default=cls.sportsbook2.is_default, prefered=False)

        cls.opportunity21.add_parent(cls.opportunity11)
        
        cls.odd_models1 = [
            OddModel(id=None, odd_id=1, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=2, event_id=1, market_id='21', sportsbook_id=cls.sportsbook1.pk, description='Vyhra *1*'),
            OddModel(id=None, odd_id=2, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=1.9, event_id=1, market_id='12', sportsbook_id=cls.sportsbook1.pk, description='Vyhra *2*'),
            OddModel(id=None, odd_id=3, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=2.1, event_id=2, market_id='21', sportsbook_id=cls.sportsbook1.pk, description='Vyhra *1*'),
            OddModel(id=None, odd_id=4, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=1.7, event_id=2, market_id='12', sportsbook_id=cls.sportsbook1.pk, description='Vyhra *2*'),
            OddModel(id=None, odd_id=5, code=0, movement=0, is_default=cls.sportsbook1.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='12', sportsbook_id=cls.sportsbook1.pk, description='Vyhra *2*'),
        ]
        cls.odd_models2 = [
            OddModel(id=None, odd_id=1, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2.1, event_id=1, market_id='13', sportsbook_id=cls.sportsbook2.pk, description='Vyhra *1*'), # this should be linked
            OddModel(id=None, odd_id=2, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=1, market_id='31', sportsbook_id=cls.sportsbook2.pk, description='Vyhra *2*'), # this should not be linked, because opportunities are not linked
            OddModel(id=None, odd_id=3, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2.2, event_id=2, market_id='13', sportsbook_id=cls.sportsbook2.pk, description='Vyhra *1*'), # this should be linked
            OddModel(id=None, odd_id=4, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='13', sportsbook_id=cls.sportsbook2.pk, description='Vyhra *1*'), # this should not be linked, because its event is not linked
            OddModel(id=None, odd_id=5, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=3, market_id='3441', sportsbook_id=cls.sportsbook2.pk, description='Unnknown opportunity'), # this wont be created
            OddModel(id=None, odd_id=6, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=3, market_id='3441', sportsbook_id=cls.sportsbook2.pk, description='Unnknown opportunity'), # this wont be created
            OddModel(id=None, odd_id=7, code=0, movement=0, is_default=cls.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=8, market_id='3441', sportsbook_id=cls.sportsbook2.pk, description='Vyhra *1*'), # this wont be created
        ]   
        
    def test_clear_unused_events(self): 
        # Arrange
        self.run_updates()
        self.assertEqual(Event.objects.count(), 6)
        sportsbook = Sportsbook.objects.first()
        sportsbook.selected = False
        sportsbook.save()

        # Act
        ScrapeHelper.clear_unused_events()

        # Assert
        self.assertEqual(Event.objects.count(), 3)
        sportsbook = Sportsbook.objects.first()
        sportsbook.selected = True
        sportsbook.save()

    def test_link_events_and_odds(self): 
        # Arrange
        self.run_updates()

        # Act
        ScrapeHelper.link_events_and_odds()

        # Assert
        event_ids = [event.event_id for event in Event.objects.filter(sportsbook=self.sportsbook2, parent__isnull=False).all()]
        self.assertEqual(event_ids, [1, 2])        
        odd_ids = [odd.odd_id for odd in Odd.objects.filter(sportsbook=self.sportsbook2, parent__isnull=False).all()]
        self.assertEqual(odd_ids, [1, 3])

    def test_chage_of_parents(self):
        # this should be better match as first eventModel in event_models2 
        self.event_models2.append(
            EventModel(None, 4, 0, "", 'Roger Federe', 'Rafael Nada', False, False, self.sportsbook2.pk, self.sport.pk, [], 5),
        )
        self.run_updates()
        ScrapeHelper.link_all_events()
        event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=4).first()
        self.assertEqual(event2.parent, None)
        self.assertEqual(event3.parent, event1)

        # this is the exact match, so it should change child of parent event
        self.event_models2.append(
            EventModel(None, 5, 0, "", 'Roger Federer', 'Rafael Nadal', False, False, self.sportsbook2.pk, self.sport.pk, [], 5),
        )
        self.event_helper2.update_events(self.event_models2)
        ScrapeHelper.link_all_events()
        event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=4).first()
        event4 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=5).first()
        self.assertEqual(event2.parent, None)
        self.assertEqual(event3.parent, None)
        self.assertEqual(event4.parent, event1)

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events(self, mock_broadcast_data): 
        # Arrange
        # we need to reset database and setup it again, otherwise there would be a mismatch between primary keys in database and in mock json files
        reset_database()
        self.setUpTestData()
        self.run_updates()
        ScrapeHelper.link_events_and_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd.movement=1
        odd.selected=True
        odd.save()
        event2 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=2).first()
        event2.selected=True
        event2.save()
        odd2 = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=3).first()
        odd2.selected=True
        odd2.save()

        # opportunity should be sent only if event is selected, odd is selected and its odd movement is up or down or fetch_all is True
        for fetch_all in [False, True]:
            if fetch_all: 
                file_path = 'scrape_server/database/Tests/test_objects/views/responses/send_updated_events_all.json'
            else:
                file_path = 'scrape_server/database/Tests/test_objects/views/responses/send_updated_events.json'   
            with open(file_path, 'r') as file:
                mock_response = json.load(file)

            # Act 
            ScrapeHelper.send_updated_events(fetch_all)
            
            # Assert
            args, _ = mock_broadcast_data.call_args
            self.assertEqual(args[0], DataType.MATCHDATA)
            json_response = args[1]
            self.normalize_opp_names(json_response)
            self.assertEqual(mock_response, json_response)

        
    def normalize_opp_names(self, json_response): 
        for opp in json_response["opportunities"]: 
            opp["opp_name"] = opp["opp_name"][0] 

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_parent_is_used(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        ScrapeHelper.link_events_and_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.used=True
        event.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd.movement=1
        odd.selected=True
        odd.save()

        # Act 
        ScrapeHelper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_child_is_used(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        ScrapeHelper.link_events_and_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        event2.used=True
        event2.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd.movement=1
        odd.selected=True
        odd.save()

        # Act 
        ScrapeHelper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_parent_odd_is_locked(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        ScrapeHelper.link_events_and_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd.movement=1
        odd.selected=True
        odd.locked=True
        odd.save()

        # Act 
        ScrapeHelper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_child_odd_is_locked(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        ScrapeHelper.link_events_and_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd.movement=1
        odd.selected=True
        odd.save()

        odd2 = Odd.objects.filter(sportsbook=self.sportsbook2, odd_id=1).first()
        odd2.movement=1
        odd2.locked=True
        odd2.save()

        # Act 
        ScrapeHelper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])    

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_odds_have_no_movement(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        ScrapeHelper.link_events_and_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd.movement=0
        odd.selected=True
        odd.save()
        odd2 = Odd.objects.filter(sportsbook=self.sportsbook2, odd_id=1).first()
        odd2.movement=0
        odd2.save()
        # Act 
        ScrapeHelper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])    

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_ev_is_leq0(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        ScrapeHelper.link_events_and_odds()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        odd = Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
        odd.movement=1
        odd.selected=True
        odd.save()
        odd2 = Odd.objects.filter(sportsbook=self.sportsbook2, odd_id=1).first()
        odd2.movement=0
        odd2.odd=1.2
        odd2.save()
        # Act 
        ScrapeHelper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])        

    def run_updates(self): 
        self.event_helper.update_events(self.event_models1)
        self.event_helper2.update_events(self.event_models2)
        self.odd_helper.update_odds(self.odd_models1, [])
        self.odd_helper2.update_odds(self.odd_models2, [])     