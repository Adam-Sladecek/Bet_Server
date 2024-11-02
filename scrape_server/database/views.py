import json
from django.http import JsonResponse
from django.db import transaction
from database.models import Opportunity, Sportsbook, Sport, Event, Odd, SportsbookMarket
from database.Scrapes.dataclass_models import (ConfigResponse, OpportunityFactoryResponse, OpportunityChildrenResponse, 
                                               EventResponse, OddResponse, MarketResponse)
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class ConfigView(View):
    http_method_names = ['get', 'post']
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        # if not request.user.is_authenticated:
        #    return JsonResponse({'message': "Unauthorized"}, status=401)
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        try:
            response = self.get_config_response()
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)

    def post(self, request):
        try:
            data = ConfigResponse.dict_to_config_response(json.loads(request.body))
            sports_ids = {sport.id for sport in data.sports}
            sb_ids = {sb.id for sb in data.sportsbooks + data.default_sportsbooks}
            with transaction.atomic():
                Sport.objects.update(selected=False)
                Sportsbook.objects.update(selected=False)
                Sport.objects.filter(id__in=sports_ids).update(selected=True)
                Sportsbook.objects.filter(id__in=sb_ids).update(selected=True)
            return JsonResponse(self.get_config_response().dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)

    def get_all_sportsbooks(self, is_default):
        return Sportsbook.objects.order_by('id').filter(is_default=is_default).all()
    
    def get_config_response(self):
        sports = Sport.objects.order_by('id').all()
        sportsbooks = self.get_all_sportsbooks(False)
        default_sportsbooks = self.get_all_sportsbooks(True)
        return ConfigResponse.dataclass_from_models(sports, sportsbooks, default_sportsbooks)

@method_decorator(csrf_exempt, name='dispatch')
class OpportunityView(View):
    http_method_names = ['get']
    def get(self, request):
        try:
            response = self.get_opportunities_for_factory()
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)
        
    def get_opportunities_for_factory(self) -> OpportunityFactoryResponse: 
        parents = Opportunity.objects.select_related('sport', 'sportsbook').filter(is_default=True).order_by('sport__pk').all()
        opportunities = Opportunity.objects.select_related('sport', 'sportsbook', 'parent').filter(is_default=False, parent__isnull=True).order_by('sport__pk').all()
        response = OpportunityFactoryResponse.data_class_from_models(parents, opportunities)
        return response  
    
@method_decorator(csrf_exempt, name='dispatch')
class PreferedOpportunityView(View):  
    http_method_names = ['patch']
    def patch(self, request, pk: int):
        try:
            data = json.loads(request.body)
            value = bool(data.get('value'))
            with transaction.atomic():
                opportunity = Opportunity.objects.get(id=pk)
                opportunity.prefered = value
                opportunity.save()
            return JsonResponse({}, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)
        
class OpportunityChildrenView(View):          
    http_method_names = ['get']
    def get(self, request):
        try:
            response = self.get_opportunities_for_children()
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)

    def get_opportunities_for_children(self) -> OpportunityChildrenResponse:
        touples = []
        parents = Opportunity.objects.select_related('sport', 'sportsbook').prefetch_related(
            'children',
            'children__sport',
            'children__sportsbook',
        ).filter(is_default=True).all()
        for parent in parents: 
            touples.append((parent, [child for child in parent.children.all()]))

        response = OpportunityChildrenResponse.data_class_from_models(touples)
        return response
     
@method_decorator(csrf_exempt, name='dispatch')
class RemoveOpportunityChildView(View):          
    http_method_names = ['patch']
    def patch(self, request, pk: int):
        try:
            with transaction.atomic():
                opportunity = Opportunity.objects.get(id=pk)
                opportunity.remove_parent()
            return JsonResponse({}, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class AddOpportunityChildView(View):          
    http_method_names = ['patch']
    def patch(self, request, pk: int, childid: int):
        try:
            parent = Opportunity.objects.get(id=pk)
            opportunity = Opportunity.objects.get(id=childid)
            with transaction.atomic():
                opportunity.add_parent(parent)
            return JsonResponse({}, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)
            
@method_decorator(csrf_exempt, name='dispatch')
class EventView(View):
    http_method_names = ['get', 'post']
    def get(self, request):
        try:
            response = self.get_default_events()
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)

    def get_default_events(self) -> EventResponse: 
        events = Event.objects.select_related('sport', 'sportsbook').prefetch_related('odds', 'children', 'children__sportsbook').filter(is_default=True, used=False).order_by('-selected').all()
        response = EventResponse.dataclass_from_models(events)
        return response

    def post(self, request):
        try:
            data = json.loads(request.body)
            ids = data.get('ids')
            events = Event.objects.prefetch_related('odds').filter(is_default=True)
            updated_events = []
            updated_odds = []
            for event in events: 
                is_selected = event.pk in ids
                event.selected = is_selected
                updated_events.append(event)

                for odd in event.odds.all():
                    odd.selected = is_selected
                    updated_odds.append(odd)
            
            with transaction.atomic():
                Event.objects.bulk_update(updated_events, ['selected'])
                Odd.objects.bulk_update(updated_odds, ['selected'])

            return JsonResponse({}, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class UsedEventView(View):
    http_method_names = ['post']
    def post(self, request, pk: int, sbpk: int):
        try:
            event = Event.objects.prefetch_related('odds','children').get(pk=pk)
            sportsbook = Sportsbook.objects.get(pk=sbpk)
            updated_events = []
            are_all_used = True
            for child in event.children.all(): 
                if child.sportsbook == sportsbook: 
                    child.used=True
                    updated_events.append(child)
                    continue
                if not child.used: 
                    are_all_used=False

            with transaction.atomic():
                if are_all_used:
                    event.used = True
                    event.selected = False
                    event.save()
                Event.objects.bulk_update(updated_events, ['used'])
            return JsonResponse({}, status=200)  
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)      

@method_decorator(csrf_exempt, name='dispatch')
class EventOddsView(View):
    http_method_names = ['get', 'post']
    def get(self, request, pk: int):
        try:
            response = self.get_event_oppotunities(pk)
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)

    def get_event_oppotunities(self, pk: int) -> OddResponse:
        event = Event.objects.prefetch_related(
                'odds',
                'odds__sportsbook',
                'odds__opportunity',
            ).get(pk=pk)
        return OddResponse.dataclass_from_models(event.odds.order_by('-opportunity__prefered', '-selected').all(), event)    

    def post(self, request, pk: int):
        try:
            data = json.loads(request.body)
            ids = data.get('ids')
            event = Event.objects.prefetch_related('odds').get(pk=pk)
            odds_to_update = []
            for odd in event.odds.all(): 
                odd.selected = odd.pk in ids
                odds_to_update.append(odd)
            with transaction.atomic():
                Odd.objects.bulk_update(odds_to_update, ['selected'])

            return JsonResponse({}, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)
        
@method_decorator(csrf_exempt, name='dispatch')
class MarketView(View): 
    http_method_names = ['get', 'put']
    def get(self, request):
        try:
            response = self.get_markets()
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400)    

    def put(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name').strip()
            sbid = data.get('sbid')
            sportsbook = Sportsbook.objects.get(pk=sbid)
            with transaction.atomic():
                SportsbookMarket.objects.create(value=name, sportsbook=sportsbook)

            response = self.get_markets()
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400) 

    def get_markets(self) -> MarketResponse:
        sportsbooks = Sportsbook.objects.prefetch_related('markets').all()
        return MarketResponse.data_class_from_models(sportsbooks)
    
@method_decorator(csrf_exempt, name='dispatch')
class DeleteMarketView(View): 
    http_method_names = ['delete']    
    def delete(self, request, pk: int):
        try:
            with transaction.atomic():
                market = SportsbookMarket.objects.get(pk=pk)
                market.delete()

            response = self.get_markets()
            return JsonResponse(response.dict, status=200)
        except Exception as e:
            return JsonResponse({'message': str(e)}, status=400) 

    def get_markets(self) -> MarketResponse:
        sportsbooks = Sportsbook.objects.prefetch_related('markets').all()
        return MarketResponse.data_class_from_models(sportsbooks)          
       
# TODO: add ngrok
# TODO: users and JWT authorization