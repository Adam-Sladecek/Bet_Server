import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrape_server.settings')
django.setup()

from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.urls import reverse
import json

from database.models import Sportsbook, Sport, Event, Opportunity, Price, SportsbookMarket
from common_test_methods import reset_database

class TestConfig(APITestCase):
    @property
    def bearer_token(self):
        user = User.objects.first() or User.objects.create_user(username='testuser', password='password')
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION":f'Bearer {refresh.access_token}'}
    
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.sportsbook1 = Sportsbook.objects.create(name="Nike", selected=True)
        cls.sportsbook2 = Sportsbook.objects.create(name="Tipsport")
        cls.default_sportsbook1 = Sportsbook.objects.create(name="Pinnacle", selected=True, is_default=True)
        cls.default_sportsbook2 = Sportsbook.objects.create(name="PS3838", is_default=True)
        cls.sport1 = Sport.objects.create(name="Football", selected=True)
        cls.sport2 = Sport.objects.create(name="Hockey")
        cls.client = APIClient()

    def test_get_config(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/get_config.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response = self.client.get(reverse('config'), **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_set_config(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/requests/set_config.json'
        with open(file_path, 'r') as file:
            mock_request = json.load(file)
        response = self.client.post(reverse('config'), json.dumps(mock_request), content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/set_config.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

class TestOpportunities(APITestCase):
    @property
    def bearer_token(self):
        user = User.objects.first() or User.objects.create_user(username='testuser', password='password')
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION":f'Bearer {refresh.access_token}'}
    
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
        )
        cls.opportunity2 = Opportunity.objects.create(
            description='1X2 *1*', 
            is_default=cls.sportsbook.is_default, 
            prefered=False,
            sportsbook= cls.sportsbook, 
            sport=cls.sport1, 
        )
        cls.opportunity3 = Opportunity.objects.create(
            description='1X2 *1*', 
            is_default=cls.sportsbook.is_default, 
            prefered=False,
            sportsbook= cls.sportsbook, 
            sport=cls.sport2, 
        )
        cls.client = APIClient()

    def test_get_opportunities_to_link(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/get_opportunities_to_link.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response = self.client.get(reverse('opportunity'), **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_add_child_to_parent_opportunity(self): 
        response = self.client.patch(reverse('add_opportunity_children', kwargs={'pk': self.opportunity1.pk, 'childid': self.opportunity1.pk}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.opportunity1.children.count(), 0)

        response = self.client.patch(reverse('add_opportunity_children', kwargs={'pk': self.opportunity1.pk, 'childid': self.opportunity3.pk}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.opportunity1.children.count(), 0)
        
        response = self.client.patch(reverse('add_opportunity_children', kwargs={'pk': self.opportunity1.pk, 'childid': self.opportunity2.pk}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.opportunity1.children.count(), 1)

    def test_get_opportunity_children(self):
        self.opportunity2.add_parent(self.opportunity1)
        self.opportunity2.save()
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/get_opportunity_children.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response = self.client.get(reverse('opportunity_children'), **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_remove_child_from_parent_opportunity(self):
        self.opportunity2.add_parent(self.opportunity1)
        self.opportunity2.save()
        response = self.client.patch(reverse('remove_opportunity_child', kwargs={'pk': self.opportunity2.pk}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.opportunity1.children.count(), 0)

    def test_set_prefered_opportunity(self):
        response = self.client.patch(reverse('preferred_opportunity', kwargs={'pk': self.opportunity1.pk}), data=json.dumps({'value': True}), content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        opp= Opportunity.objects.get(id=self.opportunity1.pk)
        self.assertTrue(opp.prefered)

class TestEvents(APITestCase):
    @property
    def bearer_token(self):
        user = User.objects.first() or User.objects.create_user(username='testuser', password='password')
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION":f'Bearer {refresh.access_token}'}
    
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
        )
        cls.price11 = Price.objects.create(
            price_id=0, 
            movement=0, 
            odds=1.1,
            is_default=cls.event1.is_default, 
            event= cls.event1, 
            sportsbook=cls.default_sportsbook, 
            opportunity=cls.opportunity1
        )
        cls.event2 = Event.objects.create(
            event_id=1, 
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
            time='', 
            home='Real M.', 
            away='Atletico M.', 
            is_default=cls.sportsbook2.is_default, 
            sportsbook=cls.sportsbook2, 
            sport=cls.sport1,
            parent=cls.event1
        )
        cls.client = APIClient()

    def test_get_monitored_events(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/events.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response = self.client.get(reverse('event'), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_change_monitored_events(self): 
        response = self.client.post(reverse('event'), data=json.dumps({'ids':[self.event1.pk]}), content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        event=Event.objects.get(id=self.event1.pk)
        self.assertTrue(event.selected)
        price=Price.objects.get(id=self.price11.pk)
        self.assertTrue(price.selected)

    def test_set_used_event(self): 
        response = self.client.post(reverse('used_event', kwargs={'pk':self.event1.pk, 'sbpk': self.sportsbook.pk}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        default_event=Event.objects.get(id=self.event1.pk)
        event1=Event.objects.get(id=self.event2.pk)
        event2=Event.objects.get(id=self.event3.pk)
        self.assertFalse(default_event.used)
        self.assertTrue(event1.used)
        self.assertFalse(event2.used)
        response = self.client.post(reverse('used_event', kwargs={'pk':self.event1.pk, 'sbpk': self.sportsbook2.pk}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        default_event=Event.objects.get(id=self.event1.pk)
        event1=Event.objects.get(id=self.event2.pk)
        event2=Event.objects.get(id=self.event3.pk)
        self.assertTrue(default_event.used)
        self.assertTrue(event1.used)
        self.assertTrue(event2.used)

    def test_get_event_prices(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/prices.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response = self.client.get(reverse('event_prices', kwargs={'pk':self.event1.pk}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)

    def test_change_event_prices(self): 
        response = self.client.post(reverse('event_prices', kwargs={'pk':self.event1.pk}), data=json.dumps({'ids':[self.price11.pk]}), content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)
        price=Price.objects.get(id=self.price11.pk)
        self.assertTrue(price.selected)

class TestMarkets(APITestCase):
    @property
    def bearer_token(self):
        user = User.objects.first() or User.objects.create_user(username='testuser', password='password')
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION":f'Bearer {refresh.access_token}'}
    
    @classmethod
    def setUpTestData(cls):
        reset_database()
        cls.default_sportsbook = Sportsbook.objects.create(name="Pinnacle", selected=True, is_default=True)
        cls.sportsbook = Sportsbook.objects.create(name="Nike", selected=True)
        cls.client = APIClient()

    def test_add_and_remove_market(self): 
        file_path = 'scrape_server/database/Tests/test_objects/views/responses/add_market.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)

        response = self.client.put(reverse('market'), data=json.dumps({'name': 'moneyline', 'sbid': 1}), content_type='application/json', **self.bearer_token)
        response = self.client.put(reverse('market'), data=json.dumps({'name': 'WDL', 'sbid': 2}), content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)    
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)
        self.assertEqual(SportsbookMarket.objects.count(), 2)

        get_response = self.client.get(reverse('market'), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(get_response.status_code, 200)    
        self.assertEqual(get_response.content, response.content)

        file_path = 'scrape_server/database/Tests/test_objects/views/responses/remove_market.json'
        with open(file_path, 'r') as file:
            mock_response = json.load(file)
        response = self.client.delete(reverse('delete_market', kwargs={'pk': 2}), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(response.status_code, 200)    
        response_content = response.content
        json_data = json.loads(response_content.decode('utf-8'))
        self.assertEqual(mock_response, json_data)
        self.assertEqual(SportsbookMarket.objects.count(), 1)

        get_response = self.client.get(reverse('market'), data={}, content_type='application/json', **self.bearer_token)
        self.assertEqual(get_response.status_code, 200)    
        self.assertEqual(get_response.content, response.content)
  