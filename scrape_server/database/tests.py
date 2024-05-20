import json
from django.test import TestCase, RequestFactory
from .enums import DataType, TaskState
from .views import delete_opportunity_link, get_config, get_opportunities_to_link, get_opportunity_links, set_config, set_opportunity_link
from .models import (Sportsbook, Sport, SportType, Event, EventLink, EventToBeLinked, ArbitrageBet, 
                     ArbitrageBetDetail, Odd, OddLink, OddToBeLinked, Opportunity, OpportunityLink, OpportunityToBeLinked)
from django.utils import timezone
from .consumers import ScrapeConsumer, broadcast_message, scrape_task_running
from unittest.mock import patch
from channels.testing import WebsocketCommunicator

class ViewTest(TestCase):
    def setUp(self):
        self.sport_type = SportType.objects.create(name="Type 1")
        self.sportsbook1 = Sportsbook.objects.create(name="Sportsbook 1", selected=True)
        self.sportsbook2 = Sportsbook.objects.create(name="Sportsbook 2", selected=True)
        self.sportsbook3 = Sportsbook.objects.create(name="Sportsbook 3", selected=False)
        self.sport1 = Sport.objects.create(name="Sport 1", selected=True, sport_type=self.sport_type)
        self.sport2 = Sport.objects.create(name="Sport 2", selected=False, sport_type=self.sport_type)
        self.opportunity = Opportunity.objects.create(sportsbook= self.sportsbook3, opp_description='Vyhrá *1*', tip_type='tp1', opp_number='32', market_id='13', bet_order=4, sport=self.sport1)
        self.opportunity2 = Opportunity.objects.create(sportsbook= self.sportsbook2, opp_description='Vyhrá *1*', tip_type='tp1', opp_number='32', market_id='13', bet_order=4, sport=self.sport1)
        self.oppbtl1 = OpportunityToBeLinked.objects.create(opportunity=self.opportunity, target_sportsbook=self.sportsbook2)
        self.oppbtl2 = OpportunityToBeLinked.objects.create(opportunity=self.opportunity2, target_sportsbook=self.sportsbook3)

    def test_get_config_success(self):
        """Test get_config function returns expected JSON response"""
        request = RequestFactory().get('/config/get')
        response = get_config(request)
        self.assertEqual(response.status_code, 200)

        expected_data = {
            'sports': [
                {'id': self.sport1.pk, 'name': self.sport1.name, 'selected': self.sport1.selected},
                {'id': self.sport2.pk, 'name': self.sport2.name, 'selected': self.sport2.selected}
            ],
            'sportsBooks': [
                {'id': self.sportsbook1.pk, 'name': self.sportsbook1.name, 'selected': self.sportsbook1.selected},
                {'id': self.sportsbook2.pk, 'name': self.sportsbook2.name, 'selected': self.sportsbook2.selected},
                {'id': self.sportsbook3.pk, 'name': self.sportsbook3.name, 'selected': self.sportsbook3.selected}
            ]
        }

        response_data = json.loads(response.content)
        self.assertEqual(response_data, expected_data)

    def test_set_config_success(self):
        """Test set_config function saves configuration successfully"""
        request_body = {
            'sports': [{'id': self.sport1.pk, 'name': self.sport1.name, 'selected': False},
                       {'id': self.sport2.pk, 'name': self.sport2.name, 'selected': True}],
            'sportsBooks': [{'id': self.sportsbook1.pk, 'name': self.sportsbook1.name, 'selected': False},
                            {'id': self.sportsbook2.pk, 'name': self.sportsbook2.name, 'selected': True}]
        }

        sport_ids = [sport['id'] for sport in request_body['sports']]
        sportsbook_ids = [sportsbook['id'] for sportsbook in request_body['sportsBooks']]

        request = RequestFactory().post('/config/set', data=json.dumps(request_body), content_type='application/json')
        response = set_config(request)
        self.assertEqual(response.status_code, 200)

        all_sports = Sport.objects.all()
        for sport in all_sports: 
            self.assertEqual(sport.selected, sport.pk in sport_ids)

        all_sportsbooks = Sportsbook.objects.all()
        for sportsbook in all_sportsbooks: 
            self.assertEqual(sportsbook.selected, sportsbook.pk in sportsbook_ids)    

    def test_set_config_exception(self):
        """Test set_config function handles exceptions"""
        request_body = {
            'invalid_key': 'invalid_value'
        }
        request = RequestFactory().post('/config/set', data=json.dumps(request_body), content_type='application/json')
        response = set_config(request)
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('message', response_data)    

    def test_get_opportunities_to_link(self):
        """Test get_opportunities_to_link function returns expected JSON response"""
        request = RequestFactory().get('/opportunitytolink/get')
        response = get_opportunities_to_link(request)
        self.assertEqual(response.status_code, 200)

        expected_data = {'data': {
            self.sportsbook1.name:[],
            self.sportsbook2.name: [
                {
                    'opportunity_id': self.opportunity.pk, 
                    'opportunity_tbl_id': self.oppbtl1.pk, 
                    'opp_description': self.opportunity.opp_description, 
                    'tip_type': self.opportunity.tip_type, 
                    'opp_number': self.opportunity.opp_number, 
                    'market_id': self.opportunity.market_id, 
                    'bet_order': self.opportunity.bet_order, 
                    'sport': self.opportunity.sport.name, 
                    'sportsbook': self.opportunity.sportsbook.name, 
                }
            ],
            self.sportsbook3.name: [
                {
                    'opportunity_id': self.opportunity2.pk, 
                    'opportunity_tbl_id': self.oppbtl2.pk, 
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
        }
        response_data = json.loads(response.content)
        self.assertEqual(response_data, expected_data)    

    def test_set_get_delete_opp_link(self):
        """Test set_opportunity_link function returns expected JSON response"""
        request_body = {
            'opportunities': [
                {
                    'opportunity_id': self.opportunity.pk, 
                    'opportunity_tbl_id': self.oppbtl1.pk, 
                    'opp_description': self.opportunity.opp_description, 
                    'tip_type': self.opportunity.tip_type, 
                    'opp_number': self.opportunity.opp_number, 
                    'market_id': self.opportunity.market_id, 
                    'bet_order': self.opportunity.bet_order, 
                    'sport': self.opportunity.sport.name, 
                    'sportsbook': self.opportunity.sportsbook.name, 
                },
                {
                    'opportunity_id': self.opportunity2.pk, 
                    'opportunity_tbl_id': self.oppbtl2.pk, 
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

        request = RequestFactory().post('/opportunitylink/set', data=json.dumps(request_body), content_type='application/json')
        response = set_opportunity_link(request)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(OpportunityToBeLinked.objects.count(), 0)
        self.assertEqual(OpportunityLink.objects.count(), 1)
        opp_link = OpportunityLink.objects.first()
        self.assertEqual(opp_link.first_opportunity.pk, request_body['opportunities'][0]['opportunity_id'])
        self.assertEqual(opp_link.second_opportunity.pk, request_body['opportunities'][1]['opportunity_id'])
        
        """Test get_opportunity_links function returns expected JSON response"""
        request = RequestFactory().get('/opportunitylink/get')
        response = get_opportunity_links(request)
        self.assertEqual(response.status_code, 200)
        opps = request_body['opportunities'].copy()
        for opp in opps: 
            del opp['opportunity_tbl_id']
            del opp['opportunity_id']
            
        expected_data = {'data': [
            {"opportunity_link_id": opp_link.pk, 
             "opportunities": opps}
        ]}
        response_data = json.loads(response.content)
        self.assertDictEqual(response_data, expected_data)  

        """Test delete_opportunity_link function returns expected JSON response"""
        request = RequestFactory().delete(f'opportunitylink/delete/{opp_link.pk}/')
        response = delete_opportunity_link(request, opp_link.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OpportunityLink.objects.count(), 0)
        self.assertEqual(OpportunityToBeLinked.objects.count(), 2)
        opps_to_be_linked = OpportunityToBeLinked.objects.all()
        first_opptbl = opps_to_be_linked[0]
        second_opptbl = opps_to_be_linked[1]
        self.assertEqual(first_opptbl.opportunity, opp_link.first_opportunity)
        self.assertEqual(second_opptbl.opportunity, opp_link.second_opportunity)
        self.assertEqual(first_opptbl.target_sportsbook, opp_link.second_opportunity.sportsbook)
        self.assertEqual(second_opptbl.target_sportsbook, opp_link.first_opportunity.sportsbook)

class ModelTest(TestCase):
    def setUp(self):
        self.sport_type = SportType.objects.create(name="WL")
        self.sport = Sport.objects.create(name="Soccer", selected=True, url="https://example.com", sport_type=self.sport_type)
        self.sportsbook = Sportsbook.objects.create(name="Sb A", selected=True, tenis_url="https://tennis.example.com")
        self.event1 = Event.objects.create(event_id=1, sportsbook=self.sportsbook, date_time=timezone.now(), first_name="Team A", second_name="Team B", sport=self.sport)
        self.event2 = Event.objects.create(event_id=2, sportsbook=self.sportsbook, date_time=timezone.now(), first_name="Team C", second_name="Team D", sport=self.sport)
        self.opportunity1 = Opportunity.objects.create(sportsbook= self.sportsbook, opp_description='desc1', tip_type='tp1', opp_number='1', market_id='2', bet_order=5, sport=self.sport)
        self.opportunity2 = Opportunity.objects.create(sportsbook= self.sportsbook, opp_description='desc2', tip_type='tp2', opp_number='2', market_id='3', bet_order=2, sport=self.sport)
        self.odd1 = Odd.objects.create(bet_id=1, tip_type='tp1', odd= 2.10, event=self.event1, sportsbook = self.sportsbook, opportunity=self.opportunity1)
        self.odd2 = Odd.objects.create(bet_id=2, tip_type='tp2', odd= 2.50, event=self.event2, sportsbook = self.sportsbook, opportunity=self.opportunity2)
        self.arbitrage_bet = ArbitrageBet.objects.create(
            first_odd_id=self.odd1.pk,
            second_odd_id=self.odd2.pk,
            sport_id=self.sport.pk,
            sport_name=self.sport.name,
            profit=10.50
        )
        self.arbitrage_bet_detail = ArbitrageBetDetail.objects.create(
            arbitrage_bet=self.arbitrage_bet,
            player_name=self.event1.first_name,
            sportsbook_name=self.sportsbook.name,
            opportunity_name=self.opportunity1.opp_description,
            odd=self.odd1.odd,
            amount=90
        )

    def test_create_event_link(self):
        """Test creating an EventLink instance"""
        event_link = EventLink.objects.create(first_event=self.event1, second_event=self.event2, score=0, sport_id=self.sport.pk)
        self.assertEqual(event_link.first_event, self.event1)
        self.assertEqual(event_link.second_event, self.event2)
        self.assertEqual(event_link.score, 0)
        self.assertEqual(event_link.sport_id, self.sport.pk)    

    def test_create_event_to_be_linked(self):
        """Test creating an EventToBeLinked instance"""
        event_to_be_linked = EventToBeLinked.objects.create(sport_id=self.sport.pk, event=self.event1, sportsbook=self.sportsbook)

        self.assertEqual(event_to_be_linked.sport_id, self.sport.pk)
        self.assertEqual(event_to_be_linked.event, self.event1)
        self.assertEqual(event_to_be_linked.sportsbook, self.sportsbook)

    def test_delete_event(self):
        """Test deleting an Event instance"""
        opportunity_link = OpportunityLink.objects.create(first_opportunity=self.opportunity1, second_opportunity=self.opportunity2)
        odd_link = OddLink.objects.create(first_odd=self.odd1, second_odd=self.odd2, sport_id=self.sport.pk, opportunity_link=opportunity_link)
        self.event1.delete()

        with self.assertRaises(OddLink.DoesNotExist):
            OddLink.objects.get(pk=odd_link.pk)

        with self.assertRaises(Odd.DoesNotExist):
            Odd.objects.get(pk=self.odd1.pk)

        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(OddLink.objects.count(), 0)
        self.assertEqual(Odd.objects.count(), 1)
        self.assertEqual(OddToBeLinked.objects.count(), 1)
        self.assertEqual(OpportunityLink.objects.count(), 1)
        self.assertTrue(OddToBeLinked.objects.filter(odd=self.odd2).exists()) 

    def test_delete_odd(self):
        """Test deleting an Odd instance"""
        opportunity_link = OpportunityLink.objects.create(first_opportunity=self.opportunity1, second_opportunity=self.opportunity2)
        odd_link = OddLink.objects.create(first_odd=self.odd1, second_odd=self.odd2, sport_id=self.sport.pk, opportunity_link=opportunity_link)
        self.odd1.delete()

        with self.assertRaises(OddLink.DoesNotExist):
            OddLink.objects.get(pk=odd_link.pk)

        with self.assertRaises(Odd.DoesNotExist):
            Odd.objects.get(pk=self.odd1.pk)

        self.assertEqual(OddLink.objects.count(), 0)
        self.assertEqual(OddToBeLinked.objects.count(), 1)
        self.assertEqual(OpportunityLink.objects.count(), 1)
        self.assertTrue(OddToBeLinked.objects.filter(odd=self.odd2).exists())

    def test_create_odd_link(self):
        """Test creating an OddLink instance"""
        opportunity_link = OpportunityLink.objects.create(first_opportunity=self.opportunity1, second_opportunity=self.opportunity2)
        odd_link = OddLink.objects.create(first_odd=self.odd1, second_odd=self.odd2, sport_id=self.sport.pk, opportunity_link=opportunity_link)
        self.assertEqual(odd_link.first_odd, self.odd1)
        self.assertEqual(odd_link.second_odd, self.odd2)
        self.assertEqual(odd_link.sport_id, self.sport.pk)
        self.assertEqual(odd_link.opportunity_link, opportunity_link)

    def test_delete_odd_link(self):
        """Test the delete method of OddLink"""
        opportunity_link = OpportunityLink.objects.create(first_opportunity=self.opportunity1, second_opportunity=self.opportunity2)
        odd_link = OddLink.objects.create(first_odd=self.odd1, second_odd=self.odd2, sport_id=self.sport.pk, opportunity_link=opportunity_link)
        odd_link.delete()
        odd_to_be_linked_1 = OddToBeLinked.objects.filter(odd=self.odd1).first()
        odd_to_be_linked_2 = OddToBeLinked.objects.filter(odd=self.odd2).first()

        self.assertIsNotNone(odd_to_be_linked_1)
        self.assertIsNotNone(odd_to_be_linked_2)

        self.assertEqual(len(OddToBeLinked.objects.all()), 2)

        self.assertEqual(odd_to_be_linked_1.sport_id, self.sport.pk)
        self.assertEqual(odd_to_be_linked_1.opportunity_link, opportunity_link)
        self.assertEqual(odd_to_be_linked_1.event, self.odd1.event)

        self.assertEqual(odd_to_be_linked_2.sport_id, self.sport.pk)
        self.assertEqual(odd_to_be_linked_2.opportunity_link, opportunity_link)
        self.assertEqual(odd_to_be_linked_2.event, self.odd2.event)
    
    def test_create_odd_to_be_linked(self):
        """Test creating an OddToBeLinked instance"""
        opportunity_link = OpportunityLink.objects.create(first_opportunity=self.opportunity1, second_opportunity=self.opportunity2)
        odd_to_be_linked = OddToBeLinked.objects.create(odd=self.odd1, sport_id=self.sport.pk, opportunity_link=opportunity_link, event=self.event1)
        self.assertEqual(odd_to_be_linked.odd, self.odd1)
        self.assertEqual(odd_to_be_linked.sport_id, self.sport.pk)
        self.assertEqual(odd_to_be_linked.opportunity_link, opportunity_link)
        self.assertEqual(odd_to_be_linked.event, self.event1)

    def test_create_opportunity_link(self):
        """Test creating an OpportunityLink"""
        opportunity_link = OpportunityLink.objects.create(
            first_opportunity=self.opportunity1,
            second_opportunity=self.opportunity2
        )
        self.assertEqual(OpportunityLink.objects.count(), 1)
        self.assertEqual(opportunity_link.first_opportunity, self.opportunity1)
        self.assertEqual(opportunity_link.second_opportunity, self.opportunity2)    

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

        await broadcast_message(DataType.STATERESPONSE, TaskState.ENDING)
        await self.should_receive(communicator1, DataType.STATERESPONSE, TaskState.ENDING)
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.ENDING)

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
        