import json
from django.test import TestCase, RequestFactory
from .views import get_config, set_config
from .models import Sportsbook, Sport, SportType, Event, EventLink, EventToBeLinked, ArbitrageBet, ArbitrageBetDetail, Odd, OddLink, OddToBeLinked, Opportunity, OpportunityLink
from django.utils import timezone

class ConfigTest(TestCase):
    def setUp(self):
        self.sport_type = SportType.objects.create(name="Type 1")
        self.sportsbook1 = Sportsbook.objects.create(name="Sportsbook 1", selected=True)
        self.sportsbook2 = Sportsbook.objects.create(name="Sportsbook 2", selected=False)
        self.sport1 = Sport.objects.create(name="Sport 1", selected=True, sport_type=self.sport_type)
        self.sport2 = Sport.objects.create(name="Sport 2", selected=False, sport_type=self.sport_type)

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
                {'id': self.sportsbook2.pk, 'name': self.sportsbook2.name, 'selected': self.sportsbook2.selected}
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

class ModelTest(TestCase):
    def setUp(self):
        self.sport_type = SportType.objects.create(name="WL")
        self.sport = Sport.objects.create(name="Soccer", selected=True, url="https://example.com", sport_type=self.sport_type)
        self.sportsbook = Sportsbook.objects.create(name="Sb A", selected=True, tenis_url="https://tennis.example.com")
        self.event1 = Event.objects.create(event_id=1, sportsbook=self.sportsbook, date_time=timezone.now(), first_name="Team A", second_name="Team B", sport=self.sport)
        self.event2 = Event.objects.create(event_id=2, sportsbook=self.sportsbook, date_time=timezone.now(), first_name="Team C", second_name="Team D", sport=self.sport)
        self.opportunity1 = Opportunity.objects.create(sportsbook= self.sportsbook, opp_description='desc1', tip_type='tp1', opp_number='1', market_id='2', bet_order=5, sport=self.sport)
        self.opportunity2 = Opportunity.objects.create(sportsbook= self.sportsbook, opp_description='desc2', tip_type='tp2', opp_number='2', market_id='3', bet_order=2, sport=self.sport)
        self.odd1 = Odd.objects.create(bet_id=1, tip_type='tp1', odd= 2.1, event=self.event1, sportsbook = self.sportsbook, opportunity=self.opportunity1)
        self.odd2 = Odd.objects.create(bet_id=2, tip_type='tp2', odd= 2.5, event=self.event2, sportsbook = self.sportsbook, opportunity=self.opportunity2)
        self.arbitrage_bet = ArbitrageBet.objects.create(
            first_odd_id=self.odd1.pk,
            second_odd_id=self.odd2.pk,
            sport_id=self.sport.pk,
            sport_name=self.sport.name,
            profit=10.50
        )
    def test_create_sport(self):
        """Test creating a Sport instance"""
        self.assertEqual(self.sport.name, "Soccer")
        self.assertTrue(self.sport.selected)
        self.assertEqual(self.sport.url, "https://example.com")
        self.assertEqual(self.sport.sport_type, self.sport_type)

    def test_create_sportsbook(self):
        """Test creating a Sportsbook instance"""
        self.assertEqual(self.sportsbook.name, "Sb A")
        self.assertTrue(self.sportsbook.selected)
        self.assertEqual(self.sportsbook.tenis_url, "https://tennis.example.com")

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

    def test_create_event(self):
        """Test creating an Event instance"""
        event = Event.objects.create(
            event_id=self.event1.pk,
            sportsbook=self.sportsbook,
            date_time=timezone.now(),
            first_name=self.event1.first_name,
            second_name=self.event1.second_name,
            sport=self.sport
        )

        self.assertEqual(event.event_id, self.event1.pk)
        self.assertEqual(event.sportsbook, self.sportsbook)
        self.assertTrue(event.date_time)
        self.assertEqual(event.first_name, self.event1.first_name)
        self.assertEqual(event.second_name, self.event1.second_name)
        self.assertEqual(event.sport, self.sport)    

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
    
    def test_create_arbitrage_bet(self):
        """Test creating an ArbitrageBet instance"""
        self.assertTrue(self.arbitrage_bet.updated)
        self.assertEqual(self.arbitrage_bet.first_odd_id, 1)
        self.assertEqual(self.arbitrage_bet.second_odd_id, 2)
        self.assertEqual(self.arbitrage_bet.sport_id, self.sport.pk)
        self.assertEqual(self.arbitrage_bet.sport_name, self.sport.name)
        self.assertEqual(self.arbitrage_bet.profit, 10.50)    

    def test_create_arbitrage_bet_detail(self):
        """Test creating an ArbitrageBetDetail instance"""
        arbitrage_bet_detail = ArbitrageBetDetail.objects.create(
            arbitrage_bet=self.arbitrage_bet,
            player_name=self.event1.first_name,
            sportsbook_name=self.sportsbook.name,
            opportunity_name=self.opportunity1.opp_description,
            odd=self.odd1.odd,
            amount=100
        )

        self.assertEqual(arbitrage_bet_detail.arbitrage_bet, self.arbitrage_bet)
        self.assertEqual(arbitrage_bet_detail.player_name, self.event1.first_name)
        self.assertEqual(arbitrage_bet_detail.sportsbook_name, self.sportsbook.name)
        self.assertEqual(arbitrage_bet_detail.opportunity_name, self.opportunity1.opp_description)
        self.assertEqual(arbitrage_bet_detail.odd, self.odd1.odd)
        self.assertEqual(arbitrage_bet_detail.amount, 100)    

    def test_create_odd(self):
        """Test creating an Odd instance"""
        self.assertEqual(self.odd1.bet_id, 1)
        self.assertEqual(self.odd1.tip_type, "tp1")
        self.assertEqual(self.odd1.odd, 2.1)
        self.assertEqual(self.odd1.event, self.event1)
        self.assertEqual(self.odd1.sportsbook, self.sportsbook)
        self.assertEqual(self.odd1.opportunity, self.opportunity1)    

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

    def test_create_opportunity(self):
        """Test creating an Opportunity"""
        self.assertEqual(self.opportunity1.sportsbook, self.sportsbook)
        self.assertEqual(self.opportunity1.opp_description, "desc1")
        self.assertEqual(self.opportunity1.tip_type, "tp1")
        self.assertEqual(self.opportunity1.opp_number, "1")
        self.assertEqual(self.opportunity1.market_id, "2")
        self.assertEqual(self.opportunity1.bet_order, 5)
        self.assertEqual(self.opportunity1.sport, self.sport)
        
    def test_create_opportunity_link(self):
        """Test creating an OpportunityLink"""
        opportunity_link = OpportunityLink.objects.create(
            first_opportunity=self.opportunity1,
            second_opportunity=self.opportunity2
        )
        self.assertEqual(OpportunityLink.objects.count(), 1)
        self.assertEqual(opportunity_link.first_opportunity, self.opportunity1)
        self.assertEqual(opportunity_link.second_opportunity, self.opportunity2)    