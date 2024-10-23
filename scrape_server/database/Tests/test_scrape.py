import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'scrape_server.settings'
django.setup()

from django.test import TestCase
import queue
import threading
from unittest.mock import patch, MagicMock

from database.Scrapes.main import scrape_fn
from database.enums import Command

"""
    This class tests overall scraping flow contained in scrape.py and scrape_service.py.
"""
class TestScrapeProcess(TestCase):
    @patch('database.models.Sport.objects.filter')
    @patch('database.models.Sportsbook.objects.filter')
    @patch('database.Scrapes.scrape_service.ScrapeHelper.link_events_and_odds')
    @patch('database.Scrapes.scrape_service.send_updated_events')
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

# class TestScrape(TestCase):
    # def setUp(self):
        # pass
        # self.sport = Sport.objects.create(name="Tennis", selected=True, url="https://example.com")
        # self.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True, is_default=True)
        # self.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        # self.event_models1 = [
        #     EventModel(None, 1, 0, "", 'Roger Federer', 'Rafael Nadal', self.sportsbook1.is_default, False, self.sportsbook1.pk, self.sport.pk, [], 5),
        #     EventModel(None, 2, 0, "", 'Novak Djokovic', 'Andy Murray', self.sportsbook1.is_default, False, self.sportsbook1.pk, self.sport.pk, [], 5),
        #     EventModel(None, 3, 0, "", 'Alexander Zverev', 'Dominic Thiem', self.sportsbook1.is_default, False, self.sportsbook1.pk, self.sport.pk, [], 5),
        # ]
        # self.event_models2 = [
        #     EventModel(None, 1, 0, "", 'Federer R.', 'Nadal R.', self.sportsbook2.is_default, False, self.sportsbook2.pk, self.sport.pk, [], 5),
        #     EventModel(None, 2, 0, "", 'Djokovic N.', 'Murray A.', self.sportsbook2.is_default, False, self.sportsbook2.pk, self.sport.pk, [], 5),
        #     EventModel(None, 3, 0, "", 'Lukas Lacko', 'Dominik Hrbaty', self.sportsbook2.is_default, False, self.sportsbook2.pk, self.sport.pk, [], 5)
        # ]

        # self.opportunity11 = Opportunity.objects.create(sportsbook= self.sportsbook1, description='Vyhrá *1*', market_id='21', sport=self.sport, is_default=self.sportsbook1.is_default, prefered=False)
        # self.opportunity12 = Opportunity.objects.create(sportsbook= self.sportsbook1, description='Vyhrá *2*', market_id='12', sport=self.sport, is_default=self.sportsbook1.is_default, prefered=False)
        
        # self.opportunity21 = Opportunity.objects.create(sportsbook= self.sportsbook2, description='Vyhrá *1*', market_id='13', sport=self.sport, is_default=self.sportsbook2.is_default, prefered=False)
        # self.opportunity22 = Opportunity.objects.create(sportsbook= self.sportsbook2, description='Vyhrá *2*', market_id='31', sport=self.sport, is_default=self.sportsbook2.is_default, prefered=False)

        # self.opportunity21.add_parent(self.opportunity11)
        
        # self.odd_models1 = [
        #     OddModel(id=None, odd_id=1, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=2, event_id=1, market_id='21', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *1*'),
        #     OddModel(id=None, odd_id=2, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=1.9, event_id=1, market_id='12', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *2*'),
        #     OddModel(id=None, odd_id=3, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=2.1, event_id=2, market_id='21', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *1*'),
        #     OddModel(id=None, odd_id=4, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=1.7, event_id=2, market_id='12', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *2*'),
        #     OddModel(id=None, odd_id=5, code=0, movement=0, is_default=self.sportsbook1.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='12', sportsbook_id=self.sportsbook1.pk, description='Vyhrá *2*'),
        # ]
        # self.odd_models2 = [
        #     OddModel(id=None, odd_id=1, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=1, market_id='13', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *1*'),
        #     OddModel(id=None, odd_id=2, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=1, market_id='31', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *2*'),
        #     OddModel(id=None, odd_id=3, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2.1, event_id=2, market_id='13', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *1*'),
        #     OddModel(id=None, odd_id=4, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2.3, event_id=3, market_id='13', sportsbook_id=self.sportsbook2.pk, description='Vyhrá *1*'),
        #     OddModel(id=None, odd_id=5, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=1.8, event_id=3, market_id='3441', sportsbook_id=self.sportsbook2.pk, description='Unnknown opportunity'),
        #     OddModel(id=None, odd_id=6, code=0, movement=0, is_default=self.sportsbook2.is_default, selected=False, locked= False, odd=2, event_id=7, market_id='3441', sportsbook_id=self.sportsbook2.pk, description='Unnknown opportunity'),
        # ]

    # def test_update_events(self):
        # pass
    #     first_batch = self.event_models1
    #     update_events(first_batch, self.sportsbook1)
    #     self.assertEqual(Event.objects.count(), 3)
    #     second_batch = self.event_models1[1:]
    #     second_batch[0] = EventModel(None, 2, 0, "new_time", 'Novak Djokovic', 'Andy Murray', False, False, 1, 1, [], 5)
    #     update_events(second_batch, self.sportsbook1)
    #     self.assertEqual(Event.objects.count(), 2)
    #     changed_event = Event.objects.filter(event_id=second_batch[0].event_id).first()
    #     assert changed_event.time == "new_time"
    #     assert changed_event.is_default
    #     all_events = Event.objects.all()
    #     event = all_events[0]
    #     event.time = "new_time1"
    #     update_selected_events([event], [all_events[1]])
    #     self.assertEqual(Event.objects.count(), 1)
    #     assert Event.objects.first().time == "new_time1"

    # def test_update_odds(self): 
    #     self.run_updates()
    #     self.assertEqual(Opportunity.objects.count(), 5)
    #     self.assertEqual(Odd.objects.count(), 9)
    #     event = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
    #     assert event.odds.count() == 2

    #     odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
    #     odd_to_update.odd = 4
    #     update_odds([], [odd_to_update], self.sportsbook1)
    #     Event.objects.filter(sportsbook=self.sportsbook1, event_id=3).delete()
    #     odd_to_update= Odd.objects.filter(sportsbook=self.sportsbook1, odd_id=1).first()
    #     self.assertEqual(Odd.objects.count(), 8)
    #     self.assertEqual(odd_to_update.odd, 4)
    #     assert Odd.objects.filter(sportsbook=self.sportsbook1, event_id=3).count() == 0
    
    # def test_get_selected_events(self): 
    #     self.run_updates()
    #     event = Event.objects.filter(sportsbook=self.sportsbook1).first()
    #     event.selected = True
    #     event.save()
    #     result, sport_ids = get_selected_events(self.sportsbook1)
    #     self.assertEqual(len(result), 1)
    #     self.assertEqual(len(sport_ids), 1)
    #     child_event = Event.objects.filter(sportsbook=self.sportsbook2).first()
    #     child_event.add_parent(event)
    #     child_event.save()
    #     result, sport_ids = get_selected_events(self.sportsbook2)
    #     self.assertEqual(len(result), 1)
    #     self.assertEqual(len(sport_ids), 1)

    # def test_clear_unused_events(self): 
    #     self.run_updates()
    #     self.sportsbook2.selected = False
    #     self.sportsbook2.save()
    #     clear_unused_events()
    #     self.assertEqual(Event.objects.count(), 3)
        
    # def test_chage_of_parents(self):
    #     self.event_models2.append(
    #         EventModel(None, 4, 0, "", 'Roger Federe', 'Rafael Nada', False, False, self.sportsbook2.pk, self.sport.pk, [], 5),
    #     )
    #     self.run_updates()
    #     link_all_events()
    #     event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
    #     event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
    #     event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=4).first()
    #     self.assertEqual(event2.parent, None)
    #     self.assertEqual(event3.parent, event1)
    #     self.event_models2.append(
    #         EventModel(None, 5, 0, "", 'Roger Federer', 'Rafael Nadal', False, False, self.sportsbook2.pk, self.sport.pk, [], 5),
    #     )
    #     update_events(self.event_models2, self.sportsbook2)
    #     link_all_events()
    #     event1 = Event.objects.filter(sportsbook=self.sportsbook1, event_id=1).first()
    #     event2 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=1).first()
    #     event3 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=4).first()
    #     event4 = Event.objects.filter(sportsbook=self.sportsbook2, event_id=5).first()
    #     self.assertEqual(event2.parent, None)
    #     self.assertEqual(event3.parent, None)
    #     self.assertEqual(event4.parent, event1)

    # def test_link_odds(self): 
    #     self.run_updates()
    #     link_all_events()
    #     link_odds()
    #     event = Event.objects.filter(sportsbook=self.sportsbook1).first()
    #     event.selected = True
    #     event.save()
    #     odd = Odd.objects.filter(sportsbook=self.sportsbook1).first()
    #     odd.selected = True
    #     odd.movement = 1
    #     odd.save()
    #     sportsbook = Sportsbook.objects.get(is_default=True, selected=True)
    #     events, _ = get_selected_events(sportsbook)
    #     response = MatchOpportunityResponse.dataclass_from_models(events, False)
    #     self.assertEqual(len(response.opportunities), 1)
    #     opportunity = response.opportunities[0]
    #     self.assertEqual(opportunity.match_id, event.pk)
    #     self.assertEqual(opportunity.parent.odd_pk, odd.pk)

    # def run_updates(self): 
    #     update_events(self.event_models1, self.sportsbook1)
    #     update_events(self.event_models2, self.sportsbook2)
    #     update_odds(self.odd_models1, [], self.sportsbook1)
    #     update_odds(self.odd_models2, [], self.sportsbook2)