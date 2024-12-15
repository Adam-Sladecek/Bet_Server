import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'scrape_server.settings'
django.setup()

from django.test import TestCase
import json 
from unittest.mock import patch

from common_test_methods import reset_database
from database.models import Sportsbook, Sport, Event, Opportunity, Odd, SportsbookMarket
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
        event = Event.objects.create(event_id=1, league_id=0, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.defaultSb, sport=cls.sport)
        SportsbookMarket.objects.create(value="LSK10110", sportsbook=cls.sportsbook)
        cls.opp = Opportunity.objects.create(description="Výsledok zápasu *1*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        cls.opp2 = Opportunity.objects.create(description="Výsledok zápasu Remíza", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        cls.opp3 = Opportunity.objects.create(description="Výsledok zápasu *2*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=1.1, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp)
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=2, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp2)
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=3, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp3)

    async def mock_fetch_import(self, session, url, sport_id, headers):
        if 'overview' in url:
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna/import_events.json'
        else:    
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna/import_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return (sport_id, mock_response)
    
    async def mock_fetch_get_data(self, session, url, sport_id, headers):
        if 'overview' in url:
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna/import_events.json'
        else:    
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna/get_data_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return (sport_id, mock_response)

    async def mock_fetch_get_data2(self, session, url, sport_id, headers):
        return (sport_id, [{"id": "LSKFOOTBALL", "leagues": [{"matches":[]}]}])
    
    def test_flow(self): 
        with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_import):
            # import_all_data
            your_instance = IfortunaScraper(self.sportsbook, [self.sport])
            your_instance.import_all_data()
            self.assertEqual(Event.objects.count(), 2)
            self.assertEqual(Odd.objects.count(), 6)

        with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_get_data):
            # get_data
            event = Event.objects.filter(is_default=False).first()
            default_event = Event.objects.filter(is_default=True).first()
            default_event.selected = True
            event.add_parent(default_event)
            event.save()
            default_event.save()
            default_odds = Odd.objects.filter(is_default=True).all()
            odds = Odd.objects.filter(is_default=False).all()
            for odd, odd_default in zip(odds, default_odds):
                odd.add_parent(odd_default)
                odd_default.selected = True
                odd_default.save()
                odd.save()
            your_instance.get_data()
            self.assertEqual(Odd.objects.filter(is_default=False, opportunity=self.opp).first().odd, 16)
            self.assertTrue(Odd.objects.filter(is_default=False, opportunity=self.opp2).first().locked)
            self.assertTrue(Odd.objects.filter(is_default=False, opportunity=self.opp3).first().locked)

        # Case: Api returns no events -> Match should be deleted with its odds
        with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_get_data2):
            # get_data
            your_instance.get_data()
            self.assertEqual(Event.objects.count(), 1)
            self.assertEqual(Odd.objects.count(), 3)

class TestNike(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True, url='football_url')
        cls.defaultSb = Sportsbook.objects.create(name="Pinacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True, is_default=False, football_url='futbal')
        event = Event.objects.create(event_id=1, league_id=0, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.defaultSb, sport=cls.sport)
        SportsbookMarket.objects.create(value="8441", sportsbook=cls.sportsbook)
        cls.opp = Opportunity.objects.create(description="Zápas - Výsledok *1*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        cls.opp2 = Opportunity.objects.create(description="Zápas - Výsledok remíza", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        cls.opp3 = Opportunity.objects.create(description="Zápas - Výsledok *2*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=1.1, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp)
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=2, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp2)
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=3, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp3)

    async def mock_fetch_import(self, session, url, sport_id, headers):
        if 'overview' in url:
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/nike/import_events.json'
        else:    
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/nike/import_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return (sport_id, mock_response)
    
    async def mock_fetch_get_data(self, session, url, sport_id, headers):
        if 'overview' in url:
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/nike/import_events.json'
        else:    
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/nike/get_data_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return (sport_id, mock_response)

    async def mock_fetch_get_data2(self, session, url, sport_id, headers):
        return (sport_id, [["/n1/overview/futbal/tournaments/",{"matches": []}]])
    
    def test_flow(self): 
        with patch.object(NikeScraper, 'fetch_data', new=self.mock_fetch_import):
            # import_all_data
            your_instance = NikeScraper(self.sportsbook, [self.sport])
            your_instance.import_all_data()
            self.assertEqual(Event.objects.count(), 2)
            self.assertEqual(Odd.objects.count(), 6)

        with patch.object(NikeScraper, 'fetch_data', new=self.mock_fetch_get_data):
            # get_data
            event= Event.objects.filter(is_default=False).first()
            default_event = Event.objects.filter(is_default=True).first()
            default_event.selected = True
            event.add_parent(default_event)
            event.save()
            default_event.save()
            default_odds = Odd.objects.filter(is_default=True).all()
            odds = Odd.objects.filter(is_default=False).all()
            for odd, odd_default in zip(odds, default_odds):
                odd.add_parent(odd_default)
                odd_default.selected = True
                odd_default.save()
                odd.save()
            your_instance.get_data()
            self.assertEqual(Odd.objects.filter(is_default=False, opportunity=self.opp).first().odd, 16)
            self.assertTrue(Odd.objects.filter(is_default=False, opportunity=self.opp2).first().locked)
            self.assertTrue(Odd.objects.filter(is_default=False, opportunity=self.opp3).first().locked)

        # Case: Api returns no events -> Match should be deleted with its odds
        with patch.object(NikeScraper, 'fetch_data', new=self.mock_fetch_get_data2):
            # get_data
            your_instance.get_data()
            self.assertEqual(Event.objects.count(), 1)
            self.assertEqual(Odd.objects.count(), 3)

class TestTipsport(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True)
        cls.defaultSb = Sportsbook.objects.create(name="Pinacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Tipsport", selected=True, is_default=False)
        event = Event.objects.create(event_id=1, league_id=0, time='', home='Real M.', away='Atletico M.', is_default=cls.defaultSb.is_default, sportsbook=cls.defaultSb, sport=cls.sport)
        SportsbookMarket.objects.create(value="16-WINNER_3W-1", sportsbook=cls.sportsbook)
        cls.opp = Opportunity.objects.create(description="Výsledok zápasu *1*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        cls.opp2 = Opportunity.objects.create(description="Výsledok zápasu Remíza", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        cls.opp3 = Opportunity.objects.create(description="Výsledok zápasu *2*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=1.1, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp)
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=2, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp2)
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=3, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=cls.opp3)

    async def mock_gather_events(self, sports):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/tipsport/import_events.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_gather_odds_import(self, events):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/tipsport/import_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return [mock_response]
    
    async def mock_gather_odds_data(self, events):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/tipsport/get_data_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return [mock_response]

    async def mock_gather_events_none(self, events):
        return {"patches": [{"value": {"matches": []}}]}
    
    def mock_get_driver(self):
        return 
    
    def test_flow(self): 
        with patch.object(TipsportScraper, 'gather_events', new=self.mock_gather_events), patch.object(TipsportScraper, 'get_driver', new=self.mock_get_driver):
            with patch.object(TipsportScraper, 'gather_odds', new=self.mock_gather_odds_import):
                # import_all_data
                your_instance = TipsportScraper(self.sportsbook, [self.sport])
                your_instance.import_all_data()
                self.assertEqual(Event.objects.count(), 2)
                self.assertEqual(Odd.objects.count(), 6)

            with patch.object(TipsportScraper, 'gather_odds', new=self.mock_gather_odds_data):
                # get_data
                event= Event.objects.filter(is_default=False).first()
                default_event = Event.objects.filter(is_default=True).first()
                default_event.selected = True
                event.add_parent(default_event)
                event.save()
                default_event.save()
                default_odds = Odd.objects.filter(is_default=True).all()
                odds = Odd.objects.filter(is_default=False).all()
                for odd, odd_default in zip(odds, default_odds):
                    odd.add_parent(odd_default)
                    odd_default.selected = True
                    odd_default.save()
                    odd.save()
                your_instance.get_data()
                self.assertEqual(Odd.objects.filter(is_default=False, opportunity=self.opp).first().odd, 16)
                self.assertTrue(Odd.objects.filter(is_default=False, opportunity=self.opp2).first().locked)
                self.assertTrue(Odd.objects.filter(is_default=False, opportunity=self.opp3).first().locked)

        # Case: Api returns no events -> Match should be deleted with its odds
        with patch.object(TipsportScraper, 'gather_events', new=self.mock_gather_events_none):
            # get_data
            your_instance.get_data()
            self.assertEqual(Event.objects.count(), 1)
            self.assertEqual(Odd.objects.count(), 3)

class TestBetfair(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True)
        cls.sportsbook = Sportsbook.objects.create(name="Betfair", selected=True, is_default=True)
        Event.objects.create(event_id=1, league_id=0, time='', home='Real Madrid', away='Atletico Madrid', is_default=cls.sportsbook.is_default, sportsbook=cls.sportsbook, sport=cls.sport)
        SportsbookMarket.objects.create(value="Match Odds", sportsbook=cls.sportsbook)

    async def mock_gather_events(self, sports, event_ids = None):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/import_events.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return {1: mock_response}
    
    async def mock_gather_events_get_data(self, sports, event_ids = None):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/import_events.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response

    async def mock_gather_odds_import(self, events, market_ids):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/import_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_gather_odds_data(self, events, market_ids):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/get_data_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_gather_markets(self, events):
        file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/betfair/markets.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return mock_response
    
    async def mock_gather_events_none(self, events, event_ids = None):
        return []
    
    def mock_get_driver(self):
        return 
    
    def test_flow(self): 
        with patch.object(BetfairScraper, 'get_driver', new=self.mock_get_driver), patch.object(BetfairScraper, 'gather_markets', new=self.mock_gather_markets):
            # import_all_data
            with patch.object(BetfairScraper, 'gather_events', new=self.mock_gather_events):
                your_instance = BetfairScraper(self.sportsbook, [self.sport])
                your_instance.import_all_data()
                self.assertEqual(Event.objects.count(), 1)
            
            # get_data
            with patch.object(BetfairScraper, 'gather_events', new=self.mock_gather_events_get_data):
                default_event = Event.objects.filter(is_default=True).first()
                default_event.selected = True
                default_event.save()
                with patch.object(BetfairScraper, 'gather_odds', new=self.mock_gather_odds_import):
                    your_instance.get_data()
                    self.assertEqual(Opportunity.objects.count(), 3)

                with patch.object(BetfairScraper, 'gather_odds', new=self.mock_gather_odds_import):
                    your_instance.get_data()
                    self.assertEqual(Odd.objects.count(), 3)
                    
                with patch.object(BetfairScraper, 'gather_odds', new=self.mock_gather_odds_data):
                    your_instance.get_data()
                    self.assertEqual(Odd.objects.filter(is_default=True, locked=False).first().odd, 16)
                    self.assertEqual(Odd.objects.filter(is_default=True, locked=True).count(), 2)

            # Case: Api returns no events -> Match should be deleted with its odds
            with patch.object(BetfairScraper, 'gather_events', new=self.mock_gather_events_none):
                # get_data
                your_instance.get_data()
                self.assertEqual(Event.objects.count(), 0)
                self.assertEqual(Odd.objects.count(), 0)