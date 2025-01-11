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
from database.models import Sportsbook, Sport, Event, Opportunity, Price
from database.Scrapes.main import scrape_fn
from database.Scrapes.dataclass_models import EventModel, PriceModel
from database.Scrapes.helpers import EventHelper, ScrapeHelper, PriceHelper

"""
    This class tests overall scraping flow contained in scrape.py and scrape_service.py.
"""
class TestScrapeProcess(TestCase):
    @patch('database.models.Sport.objects.filter')
    @patch('database.models.Sportsbook.objects.filter')
    @patch('database.Scrapes.scrape_service.ScrapeHelper')
    @patch('database.Scrapes.scrape_service.TipsportScraper')
    @patch('database.Scrapes.scrape_service.NikeScraper')
    def test_scrape_fn_with_sportsbook_data(self, mock_nike_scraper, mock_tipsport_scraper, mock_scrape_helper_class, mock_sportsbook_filter, mock_sport_filter):
        # Arrange
        mock_sportsbook_nike = MagicMock()
        mock_sportsbook_nike.pk = 1
        mock_sportsbook_nike.name = 'Nike'

        mock_sportsbook_tipsport = MagicMock()
        mock_sportsbook_tipsport.pk = 2
        mock_sportsbook_tipsport.name = 'Tipsport'

        mock_sport_filter.return_value.all.return_value = [MagicMock(name='Sport 1')]
        mock_sportsbook_filter.return_value.all.return_value = [mock_sportsbook_nike, mock_sportsbook_tipsport]

        # Mock ScrapeHelper instance and its methods
        mock_scrape_helper = MagicMock()
        mock_scrape_helper_class.return_value = mock_scrape_helper
        mock_scrape_helper.links_events = MagicMock()
        mock_scrape_helper.send_updated_events = MagicMock()
        mock_scrape_helper.link_prices = MagicMock()
        mock_scrape_helper.clear_unused_events = MagicMock()

        # Mock Nike and Tipsport scrapers
        mock_nike_scraper.return_value.__enter__.return_value = mock_nike_scraper.return_value
        mock_nike_scraper.return_value.__exit__.return_value = False
        mock_tipsport_scraper.return_value.__enter__.return_value = mock_tipsport_scraper.return_value
        mock_tipsport_scraper.return_value.__exit__.return_value = False

        mock_nike_scraper.return_value.refresh_odds = MagicMock()
        mock_tipsport_scraper.return_value.refresh_odds = MagicMock()
        mock_nike_scraper.return_value.import_events = MagicMock()
        mock_tipsport_scraper.return_value.import_events = MagicMock()

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

        mock_nike_scraper.return_value.refresh_odds.assert_called()
        mock_tipsport_scraper.return_value.refresh_odds.assert_called()
        self.assertEqual(mock_nike_scraper.return_value.import_events.call_count, 1)
        self.assertEqual(mock_tipsport_scraper.return_value.import_events.call_count, 1)

        # Assert ScrapeHelper methods were called
        mock_scrape_helper_class.assert_called_once()  # Assert constructor was called
        mock_scrape_helper.link_events.assert_called_once()
        mock_scrape_helper.send_updated_events.assert_called_once()
        mock_scrape_helper.link_prices.assert_called_once()
        mock_scrape_helper.clear_unused_events.assert_called_once()
        self.assertTrue(import_queue.empty())


class TestEventHepler(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Tennis", selected=True)
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        cls.event_helper = EventHelper(cls.sportsbook)
        cls.event_helper2 = EventHelper(cls.sportsbook2)
        cls.events = [
            Event(event_id=1, time="", home="Roger Federer", away="Rafael Nadal", is_default=cls.sportsbook.is_default, sportsbook=cls.sportsbook, sport=cls.sport),
            Event(event_id=2, time="", home="Novak Djokovic", away="Andy Murray", is_default=cls.sportsbook.is_default, sportsbook=cls.sportsbook, sport=cls.sport),
            Event(event_id=3, time="", home="Alexander Zverev", away="Dominic Thiem", is_default=cls.sportsbook.is_default, sportsbook=cls.sportsbook, sport=cls.sport),
        ]
        cls.events2 = [
            Event(event_id=1, time="", home="Federer R.", away="Nadal R.", is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport),
            Event(event_id=2, time="", home="Djokovic N.", away="Murray A.", is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport),
            Event(event_id=3, time="", home="Lukas Lacko", away="Dominik Hrbaty", is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport),
        ]

    def test_update_and_delete_events(self):
        # update_events
        first_batch = self.events
        self.event_helper.update_events(first_batch)
        self.assertEqual(Event.objects.count(), 3)

        second_batch = self.events[1:]
        second_batch[0] = Event(event_id=2, time="new_time", home="Novak Djokovic", away="Andy Murray", is_default=self.sportsbook.is_default, sportsbook=self.sportsbook, sport_id=self.sport.pk)
        self.event_helper.update_events(second_batch)
        
        self.assertEqual(Event.objects.count(), 2)
        changed_event = Event.objects.filter(event_id=second_batch[0].event_id).first()
        assert changed_event.time == "new_time"
        assert changed_event.is_default

    def test_get_selected_events(self):
        # Arrange
        self.event_helper.update_events(self.events)
        self.event_helper2.update_events(self.events2)
        self.assertEqual(Event.objects.count(), 6)
        first_event = Event.objects.filter(sportsbook=self.sportsbook, event_id=1).first()
        first_event.selected = True
        first_event.save()
        second_event = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        second_event.add_parent(first_event)
        second_event.save()

        # Act 
        default_selected_events = self.event_helper.get_selected_events()
        selected_events = self.event_helper2.get_selected_events()

        # Assert 
        self.assertEqual([e.pk for e in default_selected_events], [Event.objects.get(sportsbook=self.sportsbook, event_id=1).pk])
        self.assertEqual([e.pk for e in selected_events], [Event.objects.get(sportsbook=self.sportsbook2, event_id=1).pk])


class TestPriceHelper(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Tennis", selected=True)
        cls.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        cls.event_helper = EventHelper(cls.sportsbook1)
        cls.event_helper2 = EventHelper(cls.sportsbook2)
        cls.price_helper = PriceHelper(cls.sportsbook1)
        cls.price_helper2 = PriceHelper(cls.sportsbook2)
        cls.events1 = [
            Event(event_id=1, time="", home='Roger Federer', away='Rafael Nadal', is_default=cls.sportsbook1.is_default, sportsbook=cls.sportsbook1, sport=cls.sport),
            Event(event_id=2, time="", home='Novak Djokovic', away='Andy Murray', is_default=cls.sportsbook1.is_default, sportsbook=cls.sportsbook1, sport=cls.sport),
            Event(event_id=3, time="", home='Alexander Zverev', away='Dominic Thiem', is_default=cls.sportsbook1.is_default, sportsbook=cls.sportsbook1, sport=cls.sport),
        ]
        cls.events2 = [
            Event(event_id=1, time="", home='Federer R.', away='Nadal R.', is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport),
            Event(event_id=2, time="", home='Djokovic N.', away='Murray A.', is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport), 
            Event(event_id=3, time="", home='Lukas Lacko', away='Dominik Hrbaty', is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport)
        ]

        cls.opportunity11 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhrá *1*', sport=cls.sport, is_default=cls.sportsbook1.is_default)
        cls.opportunity12 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhrá *2*', sport=cls.sport, is_default=cls.sportsbook1.is_default)
        cls.opportunity21 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhrá *1*', sport=cls.sport, is_default=cls.sportsbook2.is_default)
        cls.opportunity22 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhrá *2*', sport=cls.sport, is_default=cls.sportsbook2.is_default)

        cls.opportunity21.add_parent(cls.opportunity11)
        
        cls.price_models1 = [
            PriceModel(id=None, description='Vyhrá *1*', price=Price(price_id=1, movement=0, odds=2, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[0], sportsbook=cls.sportsbook1)),
            PriceModel(id=None, description='Vyhrá *2*', price=Price(price_id=2, movement=0, odds=1.9, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[0], sportsbook=cls.sportsbook1)),
            PriceModel(id=None, description='Vyhrá *1*', price=Price(price_id=3, movement=0, odds=2.1, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[1], sportsbook=cls.sportsbook1)),
            PriceModel(id=None, description='Vyhrá *2*', price=Price(price_id=4, movement=0, odds=1.7, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[1], sportsbook=cls.sportsbook1)), 
            PriceModel(id=None, description='Vyhrá *2*', price=Price(price_id=5, movement=0, odds=2.3, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[2], sportsbook=cls.sportsbook1)),
        ]
        cls.price_models2 = [
            PriceModel(id=None, description='Vyhrá *1*', price=Price(price_id=1, movement=0, odds=2, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[0], sportsbook=cls.sportsbook2)),
            PriceModel(id=None, description='Vyhrá *2*', price=Price(price_id=2, movement=0, odds=1.8, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[0], sportsbook=cls.sportsbook2)),
            PriceModel(id=None, description='Vyhrá *1*', price=Price(price_id=3, movement=0, odds=2.1, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[1], sportsbook=cls.sportsbook2)),
            PriceModel(id=None, description='Vyhrá *1*', price=Price(price_id=4, movement=0, odds=2.3, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[2], sportsbook=cls.sportsbook2)),
            PriceModel(id=None, description='Unknown opportunity', price=Price(price_id=5, movement=0, odds=1.8, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[2], sportsbook=cls.sportsbook2)), # this is here to assert that odd with no matching event opportunity will be created
            PriceModel(id=None, description='Unknown opportunity', price=Price(price_id=6, movement=0, odds=2, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[1], sportsbook=cls.sportsbook2)), # this is here to assert that second odd with no matching opportunity will be created and that only one new opportunity will be added
        ]   

    def test_update_prices(self): 
        self.run_updates()
        self.assertEqual(Opportunity.objects.count(), 5)
        self.assertEqual(Price.objects.count(), 11)
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        assert event.prices.count() == 2
        price_to_update= Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price_to_update.odds = 4
        price_to_update.locked = True
        price_to_update.movement = 2
        self.price_helper.update_prices([], [price_to_update])
        Event.objects.filter(sportsbook=self.sportsbook1, event_id=3).delete()
        price_to_update= Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        self.assertEqual(Price.objects.count(), 10)
        self.assertEqual(price_to_update.odds, 4)
        self.assertTrue(price_to_update.locked)
        self.assertEqual(price_to_update.movement, 2)
        assert Price.objects.filter(sportsbook=self.sportsbook1, event_id=3).count() == 0

    def run_updates(self): 
        self.event_helper.update_events(self.events1)
        self.event_helper2.update_events(self.events2)
        self.price_helper.update_prices(self.price_models1, [])
        self.price_helper2.update_prices(self.price_models2, [])        


class TestScrapeHelper(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Tennis", selected=True)
        cls.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        cls.scrape_helper = ScrapeHelper()
        cls.event_helper = EventHelper(cls.sportsbook1)
        cls.event_helper2 = EventHelper(cls.sportsbook2)
        cls.price_helper = PriceHelper(cls.sportsbook1)
        cls.price_helper2 = PriceHelper(cls.sportsbook2)
        cls.events1 = [
            Event(event_id=1, time="", home='Roger Federer', away='Rafael Nadal', is_default=cls.sportsbook1.is_default, sportsbook=cls.sportsbook1, sport=cls.sport),
            Event(event_id=2, time="", home='Novak Djokovic', away='Andy Murray', is_default=cls.sportsbook1.is_default, sportsbook=cls.sportsbook1, sport=cls.sport),
            Event(event_id=3, time="", home='Alexander Zverev', away='Dominic Thiem', is_default=cls.sportsbook1.is_default, sportsbook=cls.sportsbook1, sport=cls.sport),
        ]
        cls.events2 = [
            Event(event_id=1, time="", home='Federer R.', away='Nadal R.', is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport),
            Event(event_id=2, time="", home='Djokovic N.', away='Murray A.', is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport),
            Event(event_id=3, time="", home='Lukas Lacko', away='Dominik Hrbaty', is_default=cls.sportsbook2.is_default, sportsbook=cls.sportsbook2, sport=cls.sport),
        ]

        cls.opportunity11 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhra *1*', sport=cls.sport, is_default=cls.sportsbook1.is_default)
        cls.opportunity12 = Opportunity.objects.create(sportsbook= cls.sportsbook1, description='Vyhra *2*', sport=cls.sport, is_default=cls.sportsbook1.is_default)
        cls.opportunity21 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhra *1*', sport=cls.sport, is_default=cls.sportsbook2.is_default)
        cls.opportunity22 = Opportunity.objects.create(sportsbook= cls.sportsbook2, description='Vyhra *2*', sport=cls.sport, is_default=cls.sportsbook2.is_default)

        cls.opportunity21.add_parent(cls.opportunity11)
        
        cls.price_models1 = [
            PriceModel(id=None, description='Vyhra *1*', price=Price(price_id=1, movement=0, odds=2, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[0], sportsbook=cls.sportsbook1)),
            PriceModel(id=None, description='Vyhra *2*', price=Price(price_id=2, movement=0, odds=1.9, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[0], sportsbook=cls.sportsbook1)),
            PriceModel(id=None, description='Vyhra *1*', price=Price(price_id=3, movement=0, odds=2.1, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[1], sportsbook=cls.sportsbook1)),
            PriceModel(id=None, description='Vyhra *2*', price=Price(price_id=4, movement=0, odds=1.7, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[1], sportsbook=cls.sportsbook1)),
            PriceModel(id=None, description='Vyhra *2*', price=Price(price_id=5, movement=0, odds=2.3, is_default=cls.sportsbook1.is_default, selected=False, locked=False, event=cls.events1[2], sportsbook=cls.sportsbook1)),
        ]
        cls.price_models2 = [
            PriceModel(id=None, description='Vyhra *1*', price=Price(price_id=1, movement=0, odds=2.1, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[0], sportsbook=cls.sportsbook2)), # this should be linked
            PriceModel(id=None, description='Vyhra *2*', price=Price(price_id=2, movement=0, odds=1.8, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[0], sportsbook=cls.sportsbook2)), # this should not be linked, because opportunities are not linked
            PriceModel(id=None, description='Vyhra *1*', price=Price(price_id=3, movement=0, odds=2.2, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[1], sportsbook=cls.sportsbook2)), # this should be linked
            PriceModel(id=None, description='Vyhra *1*', price=Price(price_id=4, movement=0, odds=2.3, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[2], sportsbook=cls.sportsbook2)), # this should not be linked, because its event is not linked
            PriceModel(id=None, description='Unknown opportunity', price=Price(price_id=5, movement=0, odds=1.8, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[2], sportsbook=cls.sportsbook2)), # this wont be created
            PriceModel(id=None, description='Unknown opportunity', price=Price(price_id=6, movement=0, odds=2.0, is_default=cls.sportsbook2.is_default, selected=False, locked=False, event=cls.events2[2], sportsbook=cls.sportsbook2)), # this wont be created
        ]
        
    def test_clear_unused_events(self): 
        # Arrange
        self.run_updates()
        self.assertEqual(Event.objects.count(), 6)
        sportsbook = Sportsbook.objects.first()
        sportsbook.selected = False
        sportsbook.save()

        # Act
        self.scrape_helper.clear_unused_events()

        # Assert
        self.assertEqual(Event.objects.count(), 3)
    
    def test_link_events_and_prices(self): 
        # Arrange
        self.run_updates()

        # Act
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()

        # Assert
        event_ids = [event.event_id for event in Event.objects.filter(sportsbook=self.sportsbook2, parent__isnull=False).all()]
        self.assertEqual(event_ids, [1, 2])        
        price_ids = [price.price_id for price in Price.objects.filter(sportsbook=self.sportsbook2, parent__isnull=False).all()]
        self.assertEqual(price_ids, [1, 3])

    def test_change_of_parents(self):
        # this should be better match as first eventModel in event_models2 
        self.events2.append(
            Event(event_id=4, time="", home='Roger Federe', away='Rafael Nada', is_default=self.sportsbook2.is_default, sportsbook=self.sportsbook2, sport=self.sport),
        )
        self.run_updates()
        self.scrape_helper.link_events()
        event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=4).first()
        self.assertEqual(event2.parent, None)
        self.assertEqual(event3.parent, event1)

        # this is the exact match, so it should change child of parent event
        self.events2.append(
            Event(event_id=5, time="", home='Roger Federer', away='Rafael Nadal', is_default=self.sportsbook2.is_default, sportsbook=self.sportsbook2, sport=self.sport),
        )
        self.event_helper2.update_events(self.events2)
        self.scrape_helper.link_events()
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
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        price = Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price.movement=1
        price.selected=True
        price.save()
        event2 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=2).first()
        event2.selected=True
        event2.save()
        price2 = Price.objects.filter(sportsbook=self.sportsbook1, price_id=3).first()
        price2.selected=True
        price2.save()

        # opportunity should be sent only if event is selected, odd is selected and its odd movement is up or down or fetch_all is True
        for fetch_all in [False, True]:
            if fetch_all: 
                file_path = 'scrape_server/database/Tests/test_objects/helpers/responses/send_updated_events_all.json'
            else:
                file_path = 'scrape_server/database/Tests/test_objects/helpers/responses/send_updated_events.json'   
            with open(file_path, 'r') as file:
                mock_response = json.load(file)

            # Act 
            self.scrape_helper.send_updated_events(fetch_all)
            
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
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.used=True
        event.save()
        price = Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price.movement=1
        price.selected=True
        price.save()

        # Act 
        self.scrape_helper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_child_is_used(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
        event2.used=True
        event2.save()
        price = Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price.movement=1
        price.selected=True
        price.save()

        # Act 
        self.scrape_helper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_parent_odd_is_locked(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        price = Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price.movement=1
        price.selected=True
        price.locked=True
        price.save()

        # Act 
        self.scrape_helper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_child_odd_is_locked(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        price = Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price.movement=1
        price.selected=True
        price.save()

        price2 = Price.objects.filter(sportsbook=self.sportsbook2, price_id=1).first()
        price2.movement=1
        price2.locked=True
        price2.save()

        # Act 
        self.scrape_helper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])    

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_odds_have_no_movement(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        price = Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price.movement=0
        price.selected=True
        price.save()
        price2 = Price.objects.filter(sportsbook=self.sportsbook2, price_id=1).first()
        price2.movement=0
        price2.save()
        # Act 
        self.scrape_helper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])    

    @patch('database.Scrapes.helpers.ScrapeHelper.broadcast_data')
    def test_send_updated_events_should_return_nothing_if_ev_is_leq0(self, mock_broadcast_data): 
        # Arrange
        self.run_updates()
        self.scrape_helper.link_events()
        self.scrape_helper.link_prices()
        event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
        event.selected=True
        event.save()
        price = Price.objects.filter(sportsbook=self.sportsbook1, price_id=1).first()
        price.movement=1
        price.selected=True
        price.save()
        price2 = Price.objects.filter(sportsbook=self.sportsbook2, price_id=1).first()
        price2.movement=0
        price2.odds=1.2
        price2.save()
        # Act 
        self.scrape_helper.send_updated_events(False)
        
        # Assert
        args, _ = mock_broadcast_data.call_args
        self.assertEqual(args[0], DataType.MATCHDATA)
        json_response = args[1]
        self.assertEqual(json_response["opportunities"], [])        

    def run_updates(self): 
        self.event_helper.update_events(self.events1)
        self.event_helper2.update_events(self.events2)
        self.price_helper.update_prices(self.price_models1, [])
        self.price_helper2.update_prices(self.price_models2, [])     