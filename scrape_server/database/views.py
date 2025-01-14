import json
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from database.models import Opportunity, Sportsbook, Sport, Event, Price, SportsbookMarket
from database.Scrapes.dataclass_models import (ConfigResponse, OpportunityFactoryResponse, OpportunityChildrenResponse, 
                                               EventResponse, PriceResponse, MarketResponse)

@method_decorator(csrf_exempt, name='dispatch')
class ConfigView(APIView):
    http_method_names = ['get', 'post']

    def get(self, request):
        try:
            response = self.get_config_response()
            return Response(response.dict, status=200)
        except Exception as e:
            return self.error_response(str(e))

    def post(self, request):
        try:
            data = self.parse_config_data(request)
            self.update_selected_items(data)
            return Response(self.get_config_response().dict, status=200)
        except Exception as e:
            return self.error_response(str(e))

    def parse_config_data(self, request) -> ConfigResponse:
        return ConfigResponse.dict_to_config_response(json.loads(request.body))

    def update_selected_items(self, data):
        sports_ids = {sport.id for sport in data.sports}
        sb_ids = {sb.id for sb in data.sportsbooks + data.default_sportsbooks}
        with transaction.atomic():
            Sport.objects.update(selected=False)
            Sportsbook.objects.update(selected=False)
            Sport.objects.filter(id__in=sports_ids).update(selected=True)
            Sportsbook.objects.filter(id__in=sb_ids).update(selected=True)

    def get_config_response(self) -> ConfigResponse:
        sports = Sport.objects.order_by('id').all()
        sportsbooks = self.get_sportsbooks(is_default=False)
        default_sportsbooks = self.get_sportsbooks(is_default=True)
        return ConfigResponse.dataclass_from_models(sports, sportsbooks, default_sportsbooks)

    def get_sportsbooks(self, is_default) -> list[Sportsbook]:
        return Sportsbook.objects.filter(is_default=is_default).order_by('id').all()

    def error_response(self, message, status=400) -> Response:
        return Response({'message': message}, status=status)

@method_decorator(csrf_exempt, name='dispatch')
class OpportunityView(APIView):
    http_method_names = ['get']
    def get(self, request):
        try:
            response = self.get_opportunities_for_factory()
            return Response(response.dict, status=200)
        except Exception as e:
            return Response({'message': str(e)}, status=400)
        
    def get_opportunities_for_factory(self) -> OpportunityFactoryResponse: 
        parents = Opportunity.objects.select_related('sport', 'sportsbook')\
            .filter(is_default=True).order_by('sport__pk').all()
        opportunities = Opportunity.objects.select_related('sport', 'sportsbook')\
            .filter(is_default=False, parent__isnull=True).order_by('sport__pk').all()
        return OpportunityFactoryResponse.data_class_from_models(parents, opportunities)
    
@method_decorator(csrf_exempt, name='dispatch')
class PreferredOpportunityView(APIView):  
    http_method_names = ['patch']
    def patch(self, request, pk: int):
        try:
            value = self.parse_value_from_request(request)
            self.update_preferred_opportunity(pk, value)
            return Response({}, status=200)
        except Exception as e:
            return Response({'message': str(e)}, status=400)

    def parse_value_from_request(self, request) -> bool:
        data = json.loads(request.body)
        return bool(data.get('value'))

    def update_preferred_opportunity(self, pk, value):
        with transaction.atomic():
            opportunity = Opportunity.objects.get(id=pk)
            opportunity.prefered = value
            opportunity.save() 

class OpportunityChildrenView(APIView):          
    http_method_names = ['get']
    def get(self, request):
        try:
            response = self.get_opportunities_for_children()
            return Response(response.dict, status=200)
        except Exception as e:
            return Response({'message': str(e)}, status=400)

    def get_opportunities_for_children(self) -> OpportunityChildrenResponse:
        parents = Opportunity.objects.select_related('sport', 'sportsbook').prefetch_related(
            'children',
            'children__sport',
            'children__sportsbook',
        ).filter(is_default=True).all()

        opportunity_tuples = [(parent, list(parent.children.all())) for parent in parents]
        response = OpportunityChildrenResponse.data_class_from_models(opportunity_tuples)
        return response
     
@method_decorator(csrf_exempt, name='dispatch')
class RemoveOpportunityChildView(APIView):          
    http_method_names = ['patch']
    def patch(self, request, pk: int):
        try:
            self.remove_parent(pk)
            return Response({}, status=200)
        except Exception as e:
            return Response({'message': str(e)}, status=400)

    def remove_parent(self, pk: int): 
        with transaction.atomic():
            opportunity = Opportunity.objects.get(id=pk)
            opportunity.remove_parent()

@method_decorator(csrf_exempt, name='dispatch')
class AddOpportunityChildView(APIView):          
    http_method_names = ['patch']
    def patch(self, request, pk: int, childid: int):
        try:
            self.add_parent(pk, childid)
            return Response({}, status=200)
        except Exception as e:
            return Response({'message': str(e)}, status=400)

    def add_parent(self, pk: int, childid: int): 
        with transaction.atomic():
            parent = Opportunity.objects.get(id=pk)
            opportunity = Opportunity.objects.get(id=childid)
            opportunity.add_parent(parent) 
            
@method_decorator(csrf_exempt, name='dispatch')
class EventView(APIView):
    http_method_names = ['get', 'post']
    def get(self, request):
        try:
            response = self.get_default_events()
            return Response(response.dict, status=200)
        except Exception as e:
            return self.error_response(str(e))

    def post(self, request):
        try:
            data = json.loads(request.body)
            event_ids = data.get('ids', [])
            self.update_selected_events_and_prices(event_ids)
            return Response({}, status=200)
        except Exception as e:
            return self.error_response(str(e))

    def get_default_events(self) -> EventResponse: 
        events = Event.objects.select_related('sport', 'sportsbook').prefetch_related('prices', 'children', 'children__sportsbook')\
            .filter(is_default=True, used=False).order_by('-selected').all()
        response = EventResponse.dataclass_from_models(events)
        return response
    
    def update_selected_events_and_prices(self, event_ids):
        events = Event.objects.prefetch_related('prices').filter(is_default=True)
        updated_events = []
        updated_prices = []

        for event in events:
            is_selected = event.pk in event_ids
            event.selected = is_selected
            updated_events.append(event)
            for price in event.prices.all():
                price.selected = is_selected
                updated_prices.append(price)

        with transaction.atomic():
            Event.objects.bulk_update(updated_events, ['selected'])
            Price.objects.bulk_update(updated_prices, ['selected'])

    def error_response(self, message, status=400) -> Response:
        return Response({'message': message}, status=status)
    
@method_decorator(csrf_exempt, name='dispatch')
class UsedEventView(APIView):
    http_method_names = ['post']
    def post(self, request, pk: int, sbpk: int):
        try:
            event, sportsbook = self.get_event_and_sportsbook(pk, sbpk)
            updated_children = self.mark_children_as_used(event, sportsbook)
            self.finalize_event_status(event, updated_children)
            return Response({}, status=200)  
        except Exception as e:
            return Response({'message': str(e)}, status=400)      

    def get_event_and_sportsbook(self, event_id: int, sportsbook_id: int) -> tuple[Event, Sportsbook]:
        event = Event.objects.prefetch_related('children', 'children__sportsbook').get(pk=event_id)
        sportsbook = Sportsbook.objects.get(pk=sportsbook_id)
        return event, sportsbook
    
    def mark_children_as_used(self, event: Event, sportsbook: Sportsbook) -> list[Event]:
        updated_children = []
        for child in event.children.all():
            if child.sportsbook == sportsbook:
                child.used = True
                updated_children.append(child)
        return updated_children
    
    def finalize_event_status(self, event: Event, updated_children: list[Event]):
        with transaction.atomic():
            if all(child.used for child in event.children.all()):
                event.used = True
                event.selected = False
                event.save()
            Event.objects.bulk_update(updated_children, ['used'])

@method_decorator(csrf_exempt, name='dispatch')
class EventPricesView(APIView):
    http_method_names = ['get', 'post']
    def get(self, request, pk: int):
        try:
            response = self.get_event_oppotunities(pk)
            return Response(response.dict, status=200)
        except Exception as e:
            return self.error_response(str(e))

    def post(self, request, pk: int):
        try:
            data = json.loads(request.body)
            ids = data.get('ids')
            if not isinstance(ids, list):
                return self.error_response("Invalid data format.")
            event = self.get_event_with_prices(pk)
            self.update_selected_prices(event, ids)
            return Response({}, status=200)
        except Exception as e:
            return self.error_response(str(e))
        
    def get_event_oppotunities(self, pk: int) -> PriceResponse:
        event = Event.objects.prefetch_related(
            'prices',
            'prices__opportunity',
        ).get(pk=pk)
        prices = event.prices.order_by('-opportunity__prefered', '-selected').all()
        return PriceResponse.dataclass_from_models(prices, event)  

    def get_event_with_prices(self, pk: int) -> list[Event]:
        return Event.objects.prefetch_related('prices').get(pk=pk)

    def update_selected_prices(self, event: Event, selected_ids: list[int]):
        prices_to_update = [
            price for price in event.prices.all() if price.selected != (price.pk in selected_ids)
        ]
        for price in prices_to_update:
            price.selected = price.pk in selected_ids

        with transaction.atomic():
            Price.objects.bulk_update(prices_to_update, ['selected'])

    def error_response(self, message, status=400):
        return Response({'message': message}, status=status)  
    
@method_decorator(csrf_exempt, name='dispatch')
class MarketView(APIView): 
    http_method_names = ['get', 'put']
    def get(self, request):
        try:
            response = self.get_markets()
            return Response(response.dict, status=200)
        except Exception as e:
            return self.error_response(str(e))  

    def put(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name').strip()
            sbid = data.get('sbid')
            if not name or not sbid:
                return self.error_response("Both 'name' and 'sbid' are required fields.")
            sportsbook = Sportsbook.objects.get(pk=sbid)
            with transaction.atomic():
                SportsbookMarket.objects.create(value=name, sportsbook=sportsbook)

            response = self.get_markets()
            return Response(response.dict, status=200)
        except Exception as e:
            return self.error_response(str(e))

    def get_markets(self) -> MarketResponse:
        sportsbooks = Sportsbook.objects.prefetch_related('markets').all()
        return MarketResponse.data_class_from_models(sportsbooks)
    
    def error_response(self, message, status=400):
        return Response({'message': message}, status=status)  
    
@method_decorator(csrf_exempt, name='dispatch')
class DeleteMarketView(APIView): 
    http_method_names = ['delete']    
    def delete(self, request, pk: int):
        try:
            with transaction.atomic():
                market = SportsbookMarket.objects.get(pk=pk)
                market.delete()

            response = self.get_markets()
            return Response(response.dict, status=200)
        except Exception as e:
            return Response({'message': str(e)}, status=400) 

    def get_markets(self) -> MarketResponse:
        sportsbooks = Sportsbook.objects.prefetch_related('markets').all()
        return MarketResponse.data_class_from_models(sportsbooks)          
       
# TODO: use docker
# TODO: run app trough provider
