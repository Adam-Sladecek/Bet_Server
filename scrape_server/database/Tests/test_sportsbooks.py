import os
import aiohttp
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'scrape_server.settings'
django.setup()

from django.test import TestCase
import json 
from unittest.mock import patch

from common_test_methods import reset_database
from database.models import Sportsbook, Sport, Event, Opportunity, Price, SportsbookMarket
from database.Scrapes.SportsBooks.ifortuna import IfortunaScraper
from database.Scrapes.SportsBooks.nike import NikeScraper
from database.Scrapes.SportsBooks.tipsport import TipsportScraper
from database.Scrapes.SportsBooks.betfair import BetfairScraper

class TestIfortuna(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True)
        cls.defaultSb = Sportsbook.objects.create(name="Pinacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="IFortuna", selected=True, is_default=False)
        event = Event.objects.create(event_id=1, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.defaultSb, sport=cls.sport)
        Event.objects.create(event_id=1, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.sportsbook, sport=cls.sport)
        SportsbookMarket.objects.create(value="LSK10110", sportsbook=cls.sportsbook)
        cls.opp = Opportunity.objects.create(description="Výsledok zápasu *1*", sportsbook=cls.sportsbook, sport=cls.sport)
        cls.opp2 = Opportunity.objects.create(description="Výsledok zápasu Remíza", sportsbook=cls.sportsbook, sport=cls.sport)
        cls.opp3 = Opportunity.objects.create(description="Výsledok zápasu *2*", sportsbook=cls.sportsbook, sport=cls.sport)
        Price.objects.create(price_id=0, movement=0, odds=1.1, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp)
        Price.objects.create(price_id=0, movement=0, odds=2, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp2)
        Price.objects.create(price_id=0, movement=0, odds=3, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp3)

    async def mock_import_events(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna/import_events.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_get_prices_first(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna/get_prices_first.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_get_prices_second(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna/get_prices_second.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response

    async def mock_api_returns_something_weird(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        return None
    
    def test_flow(self): 
        with patch.object(IfortunaScraper, 'get', new=self.mock_import_events):
            """
                Api returns 1 event. Old event should be deleted. New event should be created. 
            """
            your_instance = IfortunaScraper(self.sportsbook, [self.sport])
            your_instance.import_events()
            self.assertEqual(Event.objects.count(), 2)

        with patch.object(IfortunaScraper, 'get', new=self.mock_get_prices_first):
            """
                Api returns 3 prices. All should be added to the database. 
            """
            event = Event.objects.filter(is_default=False).first()
            default_event = Event.objects.filter(is_default=True).first()
            default_event.selected = True
            event.add_parent(default_event)
            event.save()
            default_event.save()
            default_prices = Price.objects.filter(is_default=True).all()
            prices = Price.objects.filter(is_default=False).all()
            for price, price_default in zip(prices, default_prices):
                price.add_parent(price_default)
                price_default.selected = True
                price_default.save()
                price.save()
            your_instance.refresh_prices()
            self.assertEqual(Price.objects.count(), 6)

        with patch.object(IfortunaScraper, 'get', new=self.mock_get_prices_second):
            """
                Api returns 2 prices. One should be updated. Two should be marked as locked. One because it is locked on page,
                one because it is not available. 
            """
            your_instance.refresh_prices()
            self.assertEqual(Price.objects.filter(is_default=False, opportunity=self.opp).first().odds, 16)
            self.assertEqual(Price.objects.filter(is_default=False, locked=True).count(), 2)

        with patch.object(IfortunaScraper, 'get', new=self.mock_api_returns_something_weird):
            """
                Api returns no prices. All prices should be marked as locked. 
            """
            your_instance.refresh_prices()
            self.assertEqual(Event.objects.count(), 2)
            self.assertEqual(Price.objects.count(), 6)
            self.assertEqual(Price.objects.filter(is_default=False, locked=True).count(), 3)

class TestNike(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True)
        cls.defaultSb = Sportsbook.objects.create(name="Pinacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True, is_default=False)
        event = Event.objects.create(event_id=1, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.defaultSb, sport=cls.sport)
        Event.objects.create(event_id=1, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.sportsbook, sport=cls.sport)
        SportsbookMarket.objects.create(value="8441", sportsbook=cls.sportsbook)
        cls.opp = Opportunity.objects.create(description="Zápas - Výsledok *1*", sportsbook=cls.sportsbook, sport=cls.sport)
        cls.opp2 = Opportunity.objects.create(description="Zápas - Výsledok remíza", sportsbook=cls.sportsbook, sport=cls.sport)
        cls.opp3 = Opportunity.objects.create(description="Zápas - Výsledok *2*", sportsbook=cls.sportsbook, sport=cls.sport)
        Price.objects.create(price_id=0, movement=0, odds=1.1, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp)
        Price.objects.create(price_id=0, movement=0, odds=2, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp2)
        Price.objects.create(price_id=0, movement=0, odds=3, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp3)

    async def mock_import_events(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/nike/import_events.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_get_prices_first(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/nike/get_prices_first.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response

    async def mock_get_prices_second(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/nike/get_prices_second.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response

    async def mock_api_returns_something_weird(self, session: aiohttp.ClientSession, url: str, headers: object, params: object):
        return None
    
    def test_flow(self): 
        with patch.object(NikeScraper, 'get', new=self.mock_import_events):
            """
            Api returns 1 event. Old event should be deleted. New event should be created.
            """
            your_instance = NikeScraper(self.sportsbook, [self.sport])
            your_instance.import_events()
            self.assertEqual(Event.objects.count(), 2)

        with patch.object(NikeScraper, 'get', new=self.mock_get_prices_first):
            """
            Api returns 3 prices. All should be added to the database.
            """
            event = Event.objects.filter(is_default=False).first()
            default_event = Event.objects.filter(is_default=True).first()
            default_event.selected = True
            event.add_parent(default_event)
            event.save()
            default_event.save()
            default_prices = Price.objects.filter(is_default=True).all()
            prices = Price.objects.filter(is_default=False).all()
            for price, price_default in zip(prices, default_prices):
                price.add_parent(price_default)
                price_default.selected = True
                price_default.save()
                price.save()
            your_instance.refresh_prices()
            self.assertEqual(Price.objects.count(), 6)

        with patch.object(NikeScraper, 'get', new=self.mock_get_prices_second):
            """
                Api returns 2 prices. One should be updated. Two should be marked as locked. One because it is locked on page,
                one because it is not available. 
            """
            your_instance.refresh_prices()
            self.assertEqual(Price.objects.filter(is_default=False, opportunity=self.opp).first().odds, 16)
            self.assertEqual(Price.objects.filter(is_default=False, locked=True).count(), 2)

        with patch.object(NikeScraper, 'get', new=self.mock_api_returns_something_weird):
            """
            Api returns no prices. All prices should be marked as locked.
            """
            your_instance.refresh_prices()
            self.assertEqual(Event.objects.count(), 2)
            self.assertEqual(Price.objects.count(), 6)
            self.assertEqual(Price.objects.filter(is_default=False, locked=True).count(), 3)

class TestTipsport(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True)
        cls.defaultSb = Sportsbook.objects.create(name="Pinacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Tipsport", selected=True, is_default=False)
        event = Event.objects.create(event_id=1, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.defaultSb, sport=cls.sport)
        Event.objects.create(event_id=1, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.sportsbook, sport=cls.sport)
        SportsbookMarket.objects.create(value="16-WINNER_3W-1", sportsbook=cls.sportsbook)
        cls.opp = Opportunity.objects.create(description="Výsledok zápasu *1*", sportsbook=cls.sportsbook, sport=cls.sport)
        cls.opp2 = Opportunity.objects.create(description="Výsledok zápasu Remíza", sportsbook=cls.sportsbook, sport=cls.sport)
        cls.opp3 = Opportunity.objects.create(description="Výsledok zápasu *2*", sportsbook=cls.sportsbook, sport=cls.sport)
        Price.objects.create(price_id=0, movement=0, odds=1.1, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp)
        Price.objects.create(price_id=0, movement=0, odds=2, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp2)
        Price.objects.create(price_id=0, movement=0, odds=3, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp3)

    async def mock_import_events(self, sports: list[Sport]):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/tipsport/import_events.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_get_prices_first(self, events: list[Event]):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/tipsport/get_prices_first.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return [mock_response]
    
    async def mock_get_prices_second(self, events: list[Event]):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/tipsport/get_prices_second.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return [mock_response]  

    async def mock_api_returns_something_weird(self, events: list[Event]):
        return [None]
    
    def mock_get_driver(self):
        return None
    
    def test_flow(self): 
        with patch.object(TipsportScraper, 'get_driver', new=self.mock_get_driver):
            with patch.object(TipsportScraper, 'gather_events', new=self.mock_import_events):
                """
                Api returns 1 event. Old event should be deleted. New event should be created.
                """
                your_instance = TipsportScraper(self.sportsbook, [self.sport])
                your_instance.import_events()
                self.assertEqual(Event.objects.count(), 2)

            with patch.object(TipsportScraper, 'gather_prices', new=self.mock_get_prices_first):
                """
                Api returns 3 prices. All should be added to the database.
                """
                event = Event.objects.filter(is_default=False).first()
                default_event = Event.objects.filter(is_default=True).first()
                default_event.selected = True
                event.add_parent(default_event)
                event.save()
                default_event.save()
                default_prices = Price.objects.filter(is_default=True).all()
                prices = Price.objects.filter(is_default=False).all()
                for price, price_default in zip(prices, default_prices):
                    price.add_parent(price_default)
                    price_default.selected = True
                    price_default.save()
                    price.save()
                your_instance.refresh_prices()
                self.assertEqual(Price.objects.count(), 6)
            
            with patch.object(TipsportScraper, 'gather_prices', new=self.mock_get_prices_second):
                """
                Api returns 2 prices. One should be updated. Two should be marked as locked. One because it is locked on page,
                one because it is not available.
                """
                your_instance.refresh_prices()
                self.assertEqual(Price.objects.filter(is_default=False, opportunity=self.opp).first().odds, 16)
                self.assertEqual(Price.objects.filter(is_default=False, locked=True).count(), 2)

            with patch.object(TipsportScraper, 'gather_prices', new=self.mock_api_returns_something_weird):
                """
                Api returns no prices. All prices should be marked as locked.
                """
                your_instance.refresh_prices()
                self.assertEqual(Event.objects.count(), 2)
                self.assertEqual(Price.objects.count(), 6)
                self.assertEqual(Price.objects.filter(locked=True).count(), 3)

class TestBetfair(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True)
        cls.sportsbook = Sportsbook.objects.create(name="Betfair", selected=True, is_default=True)
        Event.objects.create(event_id=1, time='', home='Real Madrid', away='Atletico Madrid', is_default=cls.sportsbook.is_default, sportsbook=cls.sportsbook, sport=cls.sport)
        SportsbookMarket.objects.create(value="Match Odds", sportsbook=cls.sportsbook)

    async def mock_import_events(self, session: aiohttp.ClientSession, url: str, headers: object, data: object):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/import_events.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_get_prices_first(self, market_ids: list[str]):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/get_prices_first.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_get_prices_second(self, market_ids: list[str]):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/get_prices_second.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_api_returns_something_weird(self, market_ids: list[str]):
        return []
    
    async def mock_gather_markets(self, event_ids: list[int]):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/markets.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    def test_flow(self): 
        with patch.object(BetfairScraper, 'post', new=self.mock_import_events):
            """
            Api returns 1 event. Old event should be deleted. New event should be created.
            """
            your_instance = BetfairScraper(self.sportsbook, [self.sport])
            your_instance.import_events()
            self.assertEqual(Event.objects.count(), 1)
            default_event = Event.objects.filter(is_default=True).first()
            default_event.selected = True
            default_event.save()

        with patch.object(BetfairScraper, 'gather_markets', new=self.mock_gather_markets):
            with patch.object(BetfairScraper, 'gather_prices', new=self.mock_get_prices_first):
                """
                Api returns 3 odds. All should be added to the database.
                """
                your_instance.refresh_prices()
                self.assertEqual(Price.objects.count(), 3)
                
            with patch.object(BetfairScraper, 'gather_prices', new=self.mock_get_prices_second):
                """
                Api returns 2 odds. One should be updated with new value (16). Two should be marked as locked.
                """
                your_instance.refresh_prices()
                self.assertEqual(Price.objects.filter(is_default=True, locked=False).first().odds, 16)
                self.assertEqual(Price.objects.filter(is_default=True, locked=True).count(), 2)

            with patch.object(BetfairScraper, 'gather_prices', new=self.mock_api_returns_something_weird):
                """
                Api returns no odds. All odds should be marked as locked.
                """
                your_instance.refresh_prices()
                self.assertEqual(Event.objects.count(), 1)
                self.assertEqual(Price.objects.filter(locked=True).count(), 3)