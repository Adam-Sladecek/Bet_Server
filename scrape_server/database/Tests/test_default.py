import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'scrape_server.settings'
django.setup()
from django.test import TestCase, RequestFactory
import json
from unittest.mock import patch
from channels.testing import WebsocketCommunicator
from database.enums import DataType, TaskState
from database.views import (set_prefered_opportunity, change_monitored_events,
                    add_child_to_parent_opportunity, remove_child_from_parent_opportunity, 
                    change_event_odds, add_market, remove_market, get_config, set_config)
from database.models import Sportsbook, Sport, Event, Opportunity, Odd, SportsbookMarket
from database.consumers import ScrapeConsumer, broadcast_message

class TestConfig(TestCase):
    @classmethod
    def setUpTestData(cls):
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

# class ViewTest(TestCase):
#     def setUp(self):
#         self.default_sportsbook1 = Sportsbook.objects.create(name="Pinnacle", selected=True, is_default=True)
#         self.default_sportsbook2 = Sportsbook.objects.create(name="PS3838", is_default=True)
#         self.sportsbook1 = Sportsbook.objects.create(name="Nike")
#         self.sportsbook2 = Sportsbook.objects.create(name="Tipsport")
#         self.sport1 = Sport.objects.create(name="Football")
#         self.sport2 = Sport.objects.create(name="Hockey")
#         self.opportunity1 = Opportunity.objects.create(
#             sportsbook= self.sportsbook1, 
#             description='Vyhrá *1*', 
#             market_id='21', 
#             sport=self.sport1, 
#             is_default=self.sportsbook1.is_default, 
#             prefered=False
#         )
#         self.opportunity2 = Opportunity.objects.create(sportsbook= self.sportsbook2, description='Vyhrá *2*', market_id='12', sport=self.sport1, is_default=self.sportsbook2.is_default, prefered=False)
#         self.event = Event.objects.create(event_id=1, time='', home='', away='', is_default=self.sportsbook1.is_default, selected=False, sportsbook=self.sportsbook1, sport=self.sport1)
#         self.odd = Odd.objects.create(odd_id=1, code=0, movement=0, odd=1.1, is_default=self.event.is_default, selected=False, locked=False, event= self.event, sportsbook=self.sportsbook1, opportunity=self.opportunity1)

#     def test_config_set_and_get_functions(self): 
#         request = RequestFactory().patch(f'/opportunity/{self.opportunity1.pk}/add/{self.opportunity2.pk}', data=json.dumps({}), content_type='application/json')
#         response = add_child_to_parent_opportunity(request, parentid=self.opportunity1.pk, childid=self.opportunity2.pk)
#         self.assertEqual(response.status_code, 200)

#     def test_views(self):
#         request = RequestFactory().patch(f'/opportunity/{self.opportunity1.pk}/add/{self.opportunity2.pk}', data=json.dumps({}), content_type='application/json')
#         response = add_child_to_parent_opportunity(request, parentid=self.opportunity1.pk, childid=self.opportunity2.pk)
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(self.opportunity1.children.count(), 1)   

#         request = RequestFactory().patch(f'/opportunity/{self.opportunity2.pk}/add/{self.opportunity1.pk}', data=json.dumps({}), content_type='application/json')
#         response = add_child_to_parent_opportunity(request, parentid=self.opportunity2.pk, childid=self.opportunity1.pk)
#         self.assertEqual(response.status_code, 400)
#         self.assertEqual(self.opportunity2.children.count(), 0)

#         request = RequestFactory().patch(f'/opportunity/children/remove/{self.opportunity2.pk}', data=json.dumps({}), content_type='application/json')
#         response = remove_child_from_parent_opportunity(request, pk=self.opportunity2.pk)
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(self.opportunity1.children.count(), 0)

#         request = RequestFactory().patch(f'/opportunity/prefered/{self.opportunity1.pk}', data=json.dumps({'value': True}), content_type='application/json')
#         response = set_prefered_opportunity(request, pk=self.opportunity1.pk)
#         self.assertEqual(response.status_code, 200)
#         opp=Opportunity.objects.get(id=self.opportunity1.pk)
#         self.assertTrue(opp.prefered)

#         event=Event.objects.first()
#         request = RequestFactory().post(f'/event/update', data=json.dumps({'ids':[event.pk]}), content_type='application/json')
#         response = change_monitored_events(request)
#         self.assertEqual(response.status_code, 200)
#         event=Event.objects.first()
#         self.assertTrue(event.selected)

#         odd= Odd.objects.first()
#         request = RequestFactory().post(f'/event/{event.pk}/odds/update', data=json.dumps({'ids':[odd.pk]}), content_type='application/json')
#         response = change_event_odds(request, pk=event.pk)
#         self.assertEqual(response.status_code, 200)
#         odd= Odd.objects.first()
#         self.assertTrue(odd.selected)    

#         request = RequestFactory().post(f'/market/add', data=json.dumps({'name': 'market1', 'sbid': self.sportsbook1.pk}), content_type='application/json')
#         response = add_market(request)
#         self.assertEqual(response.status_code, 200)
#         market = SportsbookMarket.objects.first()
#         self.assertEqual(market.value, 'market1')

#         request = RequestFactory().delete(f'/market/remove/{market.pk}', data=json.dumps({}), content_type='application/json')
#         response = remove_market(request, pk=market.pk)
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(SportsbookMarket.objects.count(), 0)    

# class ScrapeConsumerTests(TestCase):
#     @patch('threading.Thread')
#     @patch('threading.Event')
#     async def test_receive_start_end_scrape(self, thread_mock, event_mock):
#         communicator = await self.connect_communicator()
#         await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED)
#         await communicator.send_json_to({"action": "start"})
#         await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.RUNNING)

#         assert event_mock.called, 'Event should be called.'
#         assert thread_mock.called, 'Scrape thread should be called.'

#         await communicator.send_json_to({"action": "start"})
#         await self.should_receive(communicator,DataType.STATERESPONSE, TaskState.RUNNING)

#         await communicator.send_json_to({"action": "startxx"})
#         await self.should_receive_error(communicator, DataType.ERROR, "Invalid action")

#         communicator2 = await self.connect_communicator()
#         await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.RUNNING)

#         await communicator2.send_json_to({"action": "end"})
#         await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED) 
#         await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED) 

#         await communicator.send_json_to({"action": "end"})
#         await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED)
#         await communicator.disconnect()
#         await communicator2.disconnect()

#     async def test_broadcast_message(self):
#         communicator1 = await self.connect_communicator()
#         await self.should_receive(communicator1, DataType.STATERESPONSE, TaskState.CLOSED)
#         communicator2 = await self.connect_communicator()
#         await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED)

#         await broadcast_message(DataType.STATERESPONSE, TaskState.CLOSED)
#         await self.should_receive(communicator1, DataType.STATERESPONSE, TaskState.CLOSED)
#         await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED)

#         await communicator1.disconnect()
#         await communicator2.disconnect()

#     async def connect_communicator(self):
#         communicator = WebsocketCommunicator(ScrapeConsumer.as_asgi(), "/ws/scrape/")
#         connected, _ = await communicator.connect()
#         assert connected, 'Should be connected'
#         await self.should_receive(communicator, DataType.IMPORTRUNNING, TaskState.CLOSED)
#         return communicator
    
#     async def should_receive(self, communicator: WebsocketCommunicator, expected_type: DataType, expected_state: TaskState):
#         response = await communicator.receive_json_from()
#         self.assertEqual(response["type"], expected_type.value)
#         self.assertEqual(response["data"], expected_state.value)

#     async def should_receive_error(self, communicator: WebsocketCommunicator, expected_type: DataType, error: str):
#         response = await communicator.receive_json_from()
#         self.assertEqual(response["type"], expected_type.value)
#         self.assertEqual(response["data"], error)    
        