import json
from django.test import TestCase, RequestFactory
from .enums import DataType, TaskState
from .views import (delete_opportunity_link, add_parent_opportunities,
                    add_child_to_parent_opportunity, remove_child_from_parent_opportunity )
from .models import (Sportsbook, Sport, SportType, Opportunity, ParentOpportunity)
from .consumers import ScrapeConsumer, broadcast_message
from unittest.mock import patch
from channels.testing import WebsocketCommunicator

class ViewTest(TestCase):
    def setUp(self):
        self.sport_type = SportType.objects.create(name="WL")
        self.sportsbook1 = Sportsbook.objects.create(name="Sportsbook 1", selected=True)
        self.sportsbook2 = Sportsbook.objects.create(name="Sportsbook 2", selected=True)
        self.sport1 = Sport.objects.create(name="Sport 1", selected=True, sport_type=self.sport_type)
        self.sport2 = Sport.objects.create(name="Sport 2", selected=True, sport_type=self.sport_type)
        self.opportunity1 = Opportunity.objects.create(sportsbook= self.sportsbook1, opp_description='Vyhrá *1*', tip_type='tp1', opp_number='32', market_id='13', bet_order=4, sport=self.sport1)
        self.opportunity2 = Opportunity.objects.create(sportsbook= self.sportsbook2, opp_description='Vyhrá *2*', tip_type='tp1', opp_number='32', market_id='13', bet_order=4, sport=self.sport1)

    def test_parent_opportunities(self):
        """Test creating, modifying and deleting parent opportunitites."""
        request_body = {
            'opportunities': [
                {
                    'id': self.opportunity1.pk, 
                    'opp_description': self.opportunity1.opp_description, 
                    'tip_type': self.opportunity1.tip_type, 
                    'opp_number': self.opportunity1.opp_number, 
                    'market_id': self.opportunity1.market_id, 
                    'bet_order': self.opportunity1.bet_order, 
                    'sport': self.opportunity1.sport.name, 
                    'sportsbook': self.opportunity1.sportsbook.name, 
                },
                {
                    'id': self.opportunity2.pk, 
                    'opp_description': self.opportunity2.opp_description, 
                    'tip_type': self.opportunity2.tip_type, 
                    'opp_number': self.opportunity2.opp_number, 
                    'market_id': self.opportunity2.market_id, 
                    'bet_order': self.opportunity2.bet_order, 
                    'sport': self.opportunity2.sport.name, 
                    'sportsbook': self.opportunity2.sportsbook.name, 
                }
            ]
        }

        request = RequestFactory().post('/opportunitylink/add', data=json.dumps(request_body), content_type='application/json')
        response = add_parent_opportunities(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['parents']), 2)
        self.assertEqual(len(json.loads(response.content)['opportunities']), 0)

        self.assertEqual(ParentOpportunity.objects.count(), 2)
        parents = ParentOpportunity.objects.all()
        for parent in parents: 
            self.assertEqual(parent.children.count(), 1)   

        parent = ParentOpportunity.objects.first()
        new_opp1 = Opportunity.objects.create(sportsbook= self.sportsbook1, opp_description='Vyhrá *1*', tip_type='tp2', opp_number='42', market_id='23', bet_order=5, sport=self.sport1)
        new_opp2 = Opportunity.objects.create(sportsbook= self.sportsbook1, opp_description='Vyhrá *1*', tip_type='tp2', opp_number='42', market_id='23', bet_order=5, sport=self.sport2)

        request = RequestFactory().post(f'/opportunity/{parent.pk}/add/{new_opp1.pk}', data=json.dumps({}), content_type='application/json')
        response = add_child_to_parent_opportunity(request, parentid=parent.pk, childid=new_opp1.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parent.children.count(), 2)   

        request = RequestFactory().post(f'/opportunity/{parent.pk}/add/{new_opp2.pk}', data=json.dumps({}), content_type='application/json')
        response = add_child_to_parent_opportunity(request, parentid=parent.pk, childid=new_opp2.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(parent.children.count(), 2)

        request = RequestFactory().post(f'/opportunity/children/remove/{new_opp1.pk}', data=json.dumps({}), content_type='application/json')
        response = remove_child_from_parent_opportunity(request, pk=new_opp1.pk)
        self.assertEqual(len(json.loads(response.content)['parents']), 2)
        self.assertEqual(len(json.loads(response.content)['opportunities']), 2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parent.children.count(), 1)

        request = RequestFactory().post(f'/opportunitylink/delete/{parent.pk}', data=json.dumps({}), content_type='application/json')
        response = delete_opportunity_link(request, pk=parent.pk)
        self.assertEqual(len(json.loads(response.content)['links']), 0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ParentOpportunity.objects.count(), 0)

class ScrapeConsumerTests(TestCase):
    @patch('threading.Thread')
    @patch('threading.Event')
    async def test_receive_start_end_scrape(self, thread_mock, event_mock):
        communicator = await self.connect_communicator()
        await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED)
        await communicator.send_json_to({"action": "start"})
        await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.RUNNING)

        assert event_mock.called, 'Event should be called.'
        assert thread_mock.called, 'Scrape thread should be called.'

        await communicator.send_json_to({"action": "start"})
        await self.should_receive_error(communicator, DataType.ERROR, "Invalid action")

        communicator2 = await self.connect_communicator()
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.RUNNING)

        await communicator2.send_json_to({"action": "end"})
        await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED) 
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED) 

        await communicator.send_json_to({"action": "end"})
        await self.should_receive_error(communicator, DataType.ERROR, "Invalid action")
        await communicator.disconnect()
        await communicator2.disconnect()

    async def test_broadcast_message(self):
        communicator1 = await self.connect_communicator()
        await self.should_receive(communicator1, DataType.STATERESPONSE, TaskState.CLOSED)
        communicator2 = await self.connect_communicator()
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED)

        await broadcast_message(DataType.STATERESPONSE, TaskState.CLOSED)
        await self.should_receive(communicator1, DataType.STATERESPONSE, TaskState.CLOSED)
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED)

        await communicator1.disconnect()
        await communicator2.disconnect()

    async def connect_communicator(self):
        communicator = WebsocketCommunicator(ScrapeConsumer.as_asgi(), "/ws/scrape/")
        connected, _ = await communicator.connect()
        assert connected, 'Should be connected'
        return communicator
    
    async def should_receive(self, communicator: WebsocketCommunicator, expected_type: DataType, expected_state: TaskState):
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], expected_type.value)
        self.assertEqual(response["data"], expected_state.value)

    async def should_receive_error(self, communicator: WebsocketCommunicator, expected_type: DataType, error: str):
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], expected_type.value)
        self.assertEqual(response["data"], error)    
        