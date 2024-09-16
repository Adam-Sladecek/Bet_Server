import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Opportunity, Sportsbook, Sport, Event, Odd, SportsbookMarket
from django.views.decorators.csrf import csrf_exempt
from .Scrapes.dataclass_models import ConfigResponse, OpportunityFactoryResponse, OpportunityChildrenResponse, EventResponse, OddResponse, MarketResponse
from django.db import transaction
# from django.middleware.csrf import get_token

@require_GET
def get_config(request):
    try:
        sports = Sport.objects.order_by('id').all()
        sportsbooks = Sportsbook.objects.order_by('id').filter(is_default=False).all()
        default_sportsbooks = Sportsbook.objects.order_by('id').filter(is_default=True).all()
        response = ConfigResponse.dataclass_from_models(sports, sportsbooks, default_sportsbooks)
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

# @require_GET
# def get_csrf_token(request):
#     token = get_token(request)
#     return JsonResponse({'csrfToken': token}) 
   
@csrf_exempt
@require_POST
def set_config(request):
    try:
        data = ConfigResponse.dict_to_config_response(json.loads(request.body))
        sports_ids = [sport.id for sport in data.sports]
        all_sports = Sport.objects.all()
        for sport in all_sports:
            sport.selected = sport.pk in sports_ids

        sb_ids = [sb.id for sb in data.sportsbooks]
        default_sb_ids = [sb.id for sb in data.default_sportsbooks]
        sb_ids.extend(default_sb_ids)

        all_sbs = Sportsbook.objects.all()
        for sb in all_sbs:
            sb.selected = sb.pk in sb_ids

        with transaction.atomic():
            Sport.objects.bulk_update(all_sports, ['selected'])
            Sportsbook.objects.bulk_update(all_sbs, ['selected'])

        regular_sbs = [sb for sb in all_sbs if not sb.is_default]
        default_sbs = [sb for sb in all_sbs if sb.is_default]
        response = ConfigResponse.dataclass_from_models(all_sports, regular_sbs, default_sbs)
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

@require_GET
def get_opportunities_to_link(request):
    try:
        response = get_opportunities_for_factory()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

@csrf_exempt
def add_child_to_parent_opportunity(request, parentid: int, childid: int):
    try: 
        parent = Opportunity.objects.get(id=parentid)
        opportunity = Opportunity.objects.get(id=childid)
        with transaction.atomic():
            opportunity.add_parent(parent)

        return JsonResponse({}, status=200)  
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)   

@require_GET
def get_opportunity_children(request):
    try:
        response = get_opportunities_for_children()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)
      
@csrf_exempt
def remove_child_from_parent_opportunity(request, pk: int):
    try:
        with transaction.atomic():
            opportunity = Opportunity.objects.get(id=pk)
            opportunity.remove_parent()

        return JsonResponse({}, status=200)  
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)   

@csrf_exempt
def set_prefered_opportunity(request, pk: int):
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

@require_GET
def get_monitored_events(request):
    try:
        response = get_default_events()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

@csrf_exempt
@require_POST
def change_monitored_events(request):
    try:
        data = json.loads(request.body)
        ids = data.get('ids')
        events = Event.objects.filter(is_default=True)
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

@csrf_exempt
def set_used_event(request, pk: int, sbpk: int):
    try:
        event = Event.objects.prefetch_related(
            'odds',
            'children',
        ).get(pk=pk)
        sportsbook = Sportsbook.objects.get(pk=sbpk)
        child_event = event.children.filter(sportsbook=sportsbook).first()
        updated_odds = []
        for odd in child_event.odds.all():
            odd.used = True
            updated_odds.append(odd)
        with transaction.atomic():
            Odd.objects.bulk_update(updated_odds, ['used'])
        return JsonResponse({}, status=200)  
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)      

@require_GET
def get_event_odds(request, pk: int):
    try:
        response = get_event_oppotunities(pk)
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)
        
@csrf_exempt
@require_POST
def change_event_odds(request, pk: int):
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
    
@require_GET
def get_all_markets(request):
    try:
        response = get_markets()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)    
    
@csrf_exempt
@require_POST
def add_market(request):
    try:
        data = json.loads(request.body)
        name = data.get('name').strip()
        sbid = data.get('sbid')
        sportsbook = Sportsbook.objects.get(pk=sbid)
        with transaction.atomic():
            SportsbookMarket.objects.create(value=name, sportsbook=sportsbook)

        response = get_markets()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400) 
    
@csrf_exempt
def remove_market(request, pk: int):
    try:
        with transaction.atomic():
            market = SportsbookMarket.objects.get(pk=pk)
            market.delete()

        response = get_markets()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)       
       
def get_opportunities_for_factory() -> OpportunityFactoryResponse: 
    parents = Opportunity.objects.select_related('sport', 'sportsbook').filter(is_default=True).order_by('sport__pk').all()
    opportunities = Opportunity.objects.select_related('sport', 'sportsbook', 'parent').filter(is_default=False, parent__isnull=True).order_by('sport__pk').all()
    response = OpportunityFactoryResponse.data_class_from_models(parents, opportunities)
    return response

def get_opportunities_for_children() -> OpportunityChildrenResponse:
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

def get_default_events() -> EventResponse: 
    events = Event.objects.select_related('sport', 'sportsbook').prefetch_related('odds', 'children', 'children__sportsbook').filter(is_default=True).order_by('-selected').all()
    response = EventResponse.dataclass_from_models(events)
    return response

def get_event_oppotunities(pk: int) -> OddResponse:
    event = Event.objects.prefetch_related(
            'odds',
            'odds__sportsbook',
            'odds__opportunity',
        ).get(pk=pk)
    return OddResponse.dataclass_from_models(event.odds.order_by('-opportunity__prefered', '-selected').all(), event)

def get_markets() -> MarketResponse:
    sportsbooks = Sportsbook.objects.prefetch_related('markets').all()
    return MarketResponse.data_class_from_models(sportsbooks)

# TODO: add ngrok
# TODO: users and JWT authorization
# TODO: after some time too many clients error is raised