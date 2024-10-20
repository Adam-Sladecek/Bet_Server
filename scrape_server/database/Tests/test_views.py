import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'scrape_server.settings'
django.setup()
from django.test import TestCase, RequestFactory
import json
from database.views import (set_prefered_opportunity, change_monitored_events,
                    add_child_to_parent_opportunity, remove_child_from_parent_opportunity, 
                    change_event_odds, add_market, remove_market, get_config, set_config, get_opportunities_to_link,
                    get_opportunity_children, get_monitored_events, set_used_event, get_event_odds, get_all_markets)
from database.models import Sportsbook, Sport, Event, Opportunity, Odd, SportsbookMarket
from common_test_methods import reset_database

class TestConfig(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport")
        cls.default_sportsbook1 = Sportsbook.objects.create(name="Pinnacle", selected=True, is_default=True)
        cls.default_sportsbook2 = Sportsbook.objects.create(name="PS3838", is_default=True)
        cls.sport1 = Sport.objects.create(name="Football", selected=True)
        cls.sport2 = Sport.objects.create(name="Hockey")

    def test_get_config(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/get_config.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        request = RequestFactory().get(f'/config/get', data={}, content_type='application/json')
        response = get_config(request)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_set_config(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/requests/set_config.json'
        with open(file_path, 'r') as file:
            mock_request = json.load(file)
        request = RequestFactory().post(f'/config/set', data=mock_request, content_type='application/json')
        response = set_config(request)
        self.assertEqual(response.status_code, 200)
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/set_config.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

class TestOpportunities(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.default_sportsbook = Sportsbook.objects.create(name="Pinnacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True)
        cls.sport1 = Sport.objects.create(name="Football")
        cls.sport2 = Sport.objects.create(name="Hockey")
        cls.opportunity1 = Opportunity.objects.create(
            description='Vyhra *1*', 
            is_default=cls.default_sportsbook.is_default, 
            prefered=False,
            sportsbook= cls.default_sportsbook, 
            sport=cls.sport1, 
            market_id='', 
        )
        cls.opportunity2 = Opportunity.objects.create(
            description='1X2 *1*', 
            is_default=cls.sportsbook.is_default, 
            prefered=False,
            sportsbook= cls.sportsbook, 
            sport=cls.sport1, 
            market_id='', 
        )
        cls.opportunity3 = Opportunity.objects.create(
            description='1X2 *1*', 
            is_default=cls.sportsbook.is_default, 
            prefered=False,
            sportsbook= cls.sportsbook, 
            sport=cls.sport2, 
            market_id='', 
        )

    def test_get_opportunities_to_link(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/get_opportunities_to_link.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        request = RequestFactory().get(f'/opportunitytolink/get', data={}, content_type='application/json')
        response = get_opportunities_to_link(request)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_add_child_to_parent_opportunity(self): 
        request = RequestFactory().get(f'/opportunity/{self.opportunity1.pk}/add/{self.opportunity1.pk}', data={}, content_type='application/json')
        response = add_child_to_parent_opportunity(request, self.opportunity1.pk, self.opportunity1.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.opportunity1.children.count(), 0)

        request = RequestFactory().get(f'/opportunity/{self.opportunity1.pk}/add/{self.opportunity3.pk}', data={}, content_type='application/json')
        response = add_child_to_parent_opportunity(request, self.opportunity1.pk, self.opportunity3.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.opportunity1.children.count(), 0)
        
        request = RequestFactory().get(f'/opportunity/{self.opportunity1.pk}/add/{self.opportunity2.pk}', data={}, content_type='application/json')
        response = add_child_to_parent_opportunity(request, self.opportunity1.pk, self.opportunity2.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.opportunity1.children.count(), 1)

    def test_get_opportunity_children(self):
        self.opportunity2.add_parent(self.opportunity1)
        self.opportunity2.save()
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/get_opportunity_children.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        request = RequestFactory().get(f'/opportunity/children/get', data={}, content_type='application/json')
        response = get_opportunity_children(request)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_remove_child_from_parent_opportunity(self):
        self.opportunity2.add_parent(self.opportunity1)
        self.opportunity2.save()
        request = RequestFactory().patch(f'/opportunity/children/remove/{self.opportunity2.pk}', data={}, content_type='application/json')
        response = remove_child_from_parent_opportunity(request, self.opportunity2.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.opportunity1.children.count(), 0)

    def test_set_prefered_opportunity(self):
        request = RequestFactory().patch(f'/opportunity/prefered/{self.opportunity1.pk}', data=json.dumps({'value': True}), content_type='application/json')
        response = set_prefered_opportunity(request, self.opportunity1.pk)
        self.assertEqual(response.status_code, 200)
        opp= Opportunity.objects.get(id=self.opportunity1.pk)
        self.assertTrue(opp.prefered)

class TestEvents(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.default_sportsbook = Sportsbook.objects.create(name="Pinnacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport", selected=True)
        cls.sport1 = Sport.objects.create(name="Football")
        # cls.sport2 = Sport.objects.create(name="Hockey")
        cls.event1 = Event.objects.create(
            event_id=0, 
            league_id=0, 
            time='', 
            home='Real Madrid', 
            away='Fc Barcelona', 
            is_default=cls.default_sportsbook.is_default, 
            sportsbook=cls.default_sportsbook, 
            sport=cls.sport1
        )
        cls.opportunity1 = Opportunity.objects.create(
            description='Vyhra *1*', 
            is_default=cls.default_sportsbook.is_default, 
            prefered=False,
            sportsbook= cls.default_sportsbook, 
            sport=cls.sport1, 
            market_id='', 
        )
        cls.odd11 = Odd.objects.create(
            odd_id=0, 
            code=0, 
            movement=0, 
            odd=1.1,
            is_default=cls.event1.is_default, 
            event= cls.event1, 
            sportsbook=cls.default_sportsbook, 
            opportunity=cls.opportunity1
        )
        cls.event2 = Event.objects.create(
            event_id=1, 
            league_id=0, 
            time='', 
            home='R. Madrid.', 
            away='Atl. Madrid', 
            is_default=cls.sportsbook.is_default, 
            sportsbook=cls.sportsbook, 
            sport=cls.sport1,
            parent=cls.event1
        )
        cls.event3 = Event.objects.create(
            event_id=1, 
            league_id=0, 
            time='', 
            home='Real M.', 
            away='Atletico M.', 
            is_default=cls.sportsbook2.is_default, 
            sportsbook=cls.sportsbook2, 
            sport=cls.sport1,
            parent=cls.event1
        )

    def test_get_monitored_events(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/events.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        request = RequestFactory().get(f'/event', data={}, content_type='application/json')
        response = get_monitored_events(request)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_change_monitored_events(self): 
        request = RequestFactory().post(f'/event/update', data=json.dumps({'ids':[self.event1.pk]}), content_type='application/json')
        response = change_monitored_events(request)
        self.assertEqual(response.status_code, 200)
        event=Event.objects.get(id=self.event1.pk)
        self.assertTrue(event.selected)
        odd=Odd.objects.get(id=self.odd11.pk)
        self.assertTrue(odd.selected)

    def test_set_used_event(self): 
        request = RequestFactory().post(f'/event/used/{self.event1.pk}/sportsbook/{self.sportsbook.pk}', data={}, content_type='application/json')
        response = set_used_event(request, self.event1.pk, self.sportsbook.pk)
        self.assertEqual(response.status_code, 200)
        default_event=Event.objects.get(id=self.event1.pk)
        event1=Event.objects.get(id=self.event2.pk)
        event2=Event.objects.get(id=self.event3.pk)
        self.assertFalse(default_event.used)
        self.assertTrue(event1.used)
        self.assertFalse(event2.used)
        request = RequestFactory().post(f'/event/used/{self.event1.pk}/sportsbook/{self.sportsbook2.pk}', data={}, content_type='application/json')
        response = set_used_event(request, self.event1.pk, self.sportsbook2.pk)
        self.assertEqual(response.status_code, 200)
        default_event=Event.objects.get(id=self.event1.pk)
        event1=Event.objects.get(id=self.event2.pk)
        event2=Event.objects.get(id=self.event3.pk)
        self.assertTrue(default_event.used)
        self.assertTrue(event1.used)
        self.assertTrue(event2.used)

    def test_get_event_odds(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/odds.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        request = RequestFactory().get(f'/event/{self.event1.pk}/odds', data={}, content_type='application/json')
        response = get_event_odds(request, self.event1.pk)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_change_event_odds(self): 
        request = RequestFactory().post(f'/event/{self.event1.pk}/odds/update', data=json.dumps({'ids':[self.odd11.pk]}), content_type='application/json')
        response = change_event_odds(request, self.event1.pk)
        self.assertEqual(response.status_code, 200)
        odd=Odd.objects.get(id=self.odd11.pk)
        self.assertTrue(odd.selected)

class TestMarkets(TestCase):
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.default_sportsbook = Sportsbook.objects.create(name="Pinnacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True)

    def test_add_and_remove_market(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/add_market.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)

        request = RequestFactory().post(f'/market/add', data=json.dumps({'name': 'moneyline', 'sbid': 1}), content_type='application/json')
        response = add_market(request)
        request = RequestFactory().post(f'/market/add', data=json.dumps({'name': 'WDL', 'sbid': 2}), content_type='application/json')
        response = add_market(request)
        self.assertEqual(response.status_code, 200)    
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)
        self.assertEqual(SportsbookMarket.objects.count(), 2)

        request = RequestFactory().get(f'/market', data={}, content_type='application/json')
        get_response = get_all_markets(request)
        self.assertEqual(get_response.status_code, 200)    
        self.assertEqual(get_response.content, response.content)

        file_path = 'scrape_server/database/Tests/test_objects/views/responses/remove_market.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        request = RequestFactory().post(f'/market/remove/2', data={}, content_type='application/json')
        response = remove_market(request, 2)
        self.assertEqual(response.status_code, 200)    
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)
        self.assertEqual(SportsbookMarket.objects.count(), 1)

        request = RequestFactory().get(f'/market', data={}, content_type='application/json')
        get_response = get_all_markets(request)
        self.assertEqual(get_response.status_code, 200)    
        self.assertEqual(get_response.content, response.content)
  