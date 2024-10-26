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
from database.Scrapes.SportsBooks.ifortuna import IfortunaScraper
from database.Scrapes.dataclass_models import EventModel, OddModel
from database.Scrapes.helpers import EventHelper, OddHelper, ScrapeHelper

class TestIfortuna(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sport = Sport.objects.create(name="Tennis", selected=True, url="https://example.com")
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)

    async def mock_fetch_events(self, session, url, sport_id, headers):
        mock_response = [{'id': 'LSKFOOTBALL'}]
        return (sport_id, mock_response)
     
    async def test_gather_events(self): 
        with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_events):
            your_instance = IfortunaScraper(self.sportsbook, [self.sport])
            results = await your_instance.gather_events([self.sport])
            print(results)
            self.assertEqual(results, {1: {'id': 'LSKFOOTBALL'}})

    async def mock_fetch_odds(self, session, url, sport_id, headers):
        mock_response = [{'id': 'LSKFOOTBALL'}]
        return (sport_id, mock_response)
     
    # async def test_gather_odds(self): 
    #     ev
    #     with patch.object(IfortunaScraper, 'fetch_data', new=self.mock_fetch_odds):
    #         your_instance = IfortunaScraper(self.sportsbook, [self.sport])
    #         results = await your_instance.gather_odds([self.sport])
    #         print(results)
    #         self.assertEqual(results, {1: {'id': 'LSKFOOTBALL'}})        