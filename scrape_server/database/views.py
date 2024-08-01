import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Opportunity, Sportsbook, Sport, Event, Odd
# from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from .Scrapes.dataclass_models import ConfigResponse, OpportunityFactoryResponse, OpportunityChildrenResponse, EventResponse, OddResponse
from django.db import transaction
from collections import defaultdict

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
@require_POST
def add_child_to_parent_opportunity(request, parentid: int, childid: int):
    try: 
        parent = Opportunity.objects.get(id=parentid)
        opportunity = Opportunity.objects.get(id=childid)
        with transaction.atomic():
            opportunity.add_parent(parent)

        response = get_opportunities_for_factory()

        return JsonResponse(response.dict, status=200)  
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

        response = get_opportunities_for_children()

        return JsonResponse(response.dict, status=200)  
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
        events = Event.objects.filter(is_default=True).all()
        for event in events: 
            event.selected = event.pk in ids
        with transaction.atomic():
            Event.objects.bulk_update(events, ['selected'])

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
        event = Event.objects.filter(pk=pk).first()
        odds_to_update = []
        for odd in event.odds.all(): 
            odd.selected = odd.pk in ids
            odds_to_update.append(odd)
        with transaction.atomic():
            Odd.objects.bulk_update(odds_to_update, ['selected'])

        return JsonResponse({}, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)
    
def get_opportunities_for_factory() -> OpportunityFactoryResponse: 
    parents = Opportunity.objects.select_related('sport').filter(is_default=True).all()
    opportunities = Opportunity.objects.select_related('sport', 'sportsbook').all()
    opportunities = [opp for opp in opportunities if not opp.has_parent]
    response = OpportunityFactoryResponse.data_class_from_models(parents, opportunities)
    return response

def get_opportunities_for_children() -> OpportunityChildrenResponse:
    opportunity_dict = defaultdict(list[Opportunity])
    parents = Opportunity.objects.select_related('sport').prefetch_related(
        'children',
        'children__sport',
        'children__sportsbook',
    ).filter(is_default=True).all()
    for parent in parents: 
        opportunity_dict[parent.opp_description] = [child for child in parent.children.all()]

    response = OpportunityChildrenResponse.data_class_from_models(opportunity_dict)
    return response 

def get_default_events() -> EventResponse: 
    events = Event.objects.select_related('sport', 'sportsbook').filter(is_default=True).order_by('-selected').all()
    response = EventResponse.dataclass_from_models(events)
    return response

def get_event_oppotunities(pk: int) -> OddResponse:
    event = Event.objects.filter(pk=pk).prefetch_related(
            'odds',
            'odds__sportsbook',
            'odds__opportunity',
            'odds__parent',
        ).first()
    return OddResponse.dataclass_from_models(event.odds.order_by('-opportunity__prefered', '-selected').all())

# TODO: add ngrok
# TODO: users and JWT authorization
# TODO: after some time too many clients error is raised