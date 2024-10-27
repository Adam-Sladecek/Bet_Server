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

class TestIfortuna(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Football", selected=True)
        cls.defaultSb = Sportsbook.objects.create(name="Pinacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="IFortuna", selected=True, is_default=False)
        event = Event.objects.create(event_id=1, league_id=0, time='', home='Real M.', away='Atletico M.', 
                                     is_default=cls.defaultSb.is_default, sportsbook=cls.defaultSb, sport=cls.sport)
        SportsbookMarket.objects.create(value="LSK10110", sportsbook=cls.sportsbook)
        opp = Opportunity.objects.create(description="Výsledok zápasu *1*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        Opportunity.objects.create(description="Výsledok zápasu Remíza", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        Opportunity.objects.create(description="Výsledok zápasu *2*", sportsbook=cls.sportsbook, sport=cls.sport, market_id="")
        Odd.objects.create(odd_id=0, code=0, movement=0, odd=1.1, is_default=event.is_default, event= event, sportsbook=cls.defaultSb, opportunity=opp)

    async def mock_fetch_import(self, session, url, sport_id, headers):
        if 'overview' in url:
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna_import_events.json'
        else:    
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna_import_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return (sport_id, mock_response)
    
    async def mock_fetch_get_data(self, session, url, sport_id, headers):
        if 'overview' in url:
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna_import_events.json'
        else:    
            file_path = 'scrape_server/database/Tests/test_objects/sportsbooks/responses/ifortuna_get_data_odds.json'
        with open(file_path, 'r', encoding='utf-8') as file:
            mock_response = json.load(file)
        return (sport_id, mock_response)

    async def mock_fetch_get_data2(self, session, url, sport_id, headers):
        return (sport_id, {})
    
    def test_flow(self): 
        with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_import):
            # import_all_data
            your_instance = IfortunaScraper(self.sportsbook, [self.sport])
            your_instance.import_all_data()
            self.assertEqual(Event.objects.count(), 2)
            self.assertEqual(Odd.objects.count(), 4)

        with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_get_data):
            # get_data
            event= Event.objects.filter(is_default=False).first()
            default_event = Event.objects.filter(is_default=True).first()
            default_event.selected = True
            event.add_parent(default_event)
            event.save()
            default_event.save()
            odd = Odd.objects.filter(is_default=False).first()
            odd_default = Odd.objects.filter(is_default=True).first()
            odd.add_parent(odd_default)
            odd_default.selected = True
            odd_default.save()
            odd.save()
            your_instance.get_data()
            self.assertEqual(Odd.objects.filter(is_default=False).first().odd, 16)

        # Case: Api returns no events -> Match should be deleted with its odds
        with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_get_data2):
            # get_data
            your_instance.get_data()
            self.assertEqual(Event.objects.count(), 1)
            self.assertEqual(Odd.objects.count(), 1)
