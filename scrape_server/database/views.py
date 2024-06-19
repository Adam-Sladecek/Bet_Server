import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Opportunity, Sportsbook, Sport, ParentOpportunity
# from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from .Scrapes.dataclass_models import ConfigResponse, OpportunityLinkResponse, OpportunityDataClass, OpportunityFactoryResponse, OpportunityChildrenResponse
from django.db import transaction
from collections import defaultdict

@require_GET
def get_config(request):
    try:
        sports = Sport.objects.order_by('id').all()
        sportsbooks = Sportsbook.objects.order_by('id').all()
        response = ConfigResponse.dataclass_from_models(sports, sportsbooks)
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
        all_sbs = Sportsbook.objects.all()
        for sb in all_sbs:
            sb.selected = sb.pk in sb_ids

        with transaction.atomic():
            Sport.objects.bulk_update(all_sports, ['selected'])
            Sportsbook.objects.bulk_update(all_sbs, ['selected'])

        response = ConfigResponse.dataclass_from_models(all_sports, all_sbs)
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

@require_GET
def get_opportunities_to_link(request):
    try:
        response = opportunities_for_factory()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

@csrf_exempt
@require_POST
def add_parent_opportunities(request):
    try: 
        opportunity_dataclasses = OpportunityDataClass.dict_to_dataclass_list(json.loads(request.body))
        opportunities = [Opportunity.objects.get(id=opp.id) for opp in opportunity_dataclasses]
        with transaction.atomic():
            parents = ParentOpportunity.create_parent_opportunities(opportunities)
            
        with transaction.atomic():
            parents[0].link_with(parents[1])
            parents[0].add_child(opportunities[0])
            parents[1].add_child(opportunities[1])

        response = opportunities_for_factory()

        return JsonResponse(response.dict, status=200)  
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)   

@csrf_exempt
@require_POST
def add_child_to_parent_opportunity(request, parentid: int, childid: int):
    try: 
        parent = ParentOpportunity.objects.get(id=parentid)
        opportunity = Opportunity.objects.get(id=childid)
        with transaction.atomic():
            parent.add_child(opportunity)

        response = opportunities_for_factory()

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
def get_opportunity_links(request):
    try:
        response = get_opportunities_for_links()

        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

@csrf_exempt
def delete_opportunity_link(request, pk: int):
    try:
        with transaction.atomic():
            ParentOpportunity.objects.get(id=pk).delete()

        response = get_opportunities_for_links()
        return JsonResponse(response.dict, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

def opportunities_for_factory() -> OpportunityFactoryResponse: 
    parents = ParentOpportunity.objects.select_related('sport').all()
    opportunities = Opportunity.objects.select_related('sport', 'sportsbook').filter(has_parent=False).all()
    response = OpportunityFactoryResponse.data_class_from_models(parents, opportunities)
    return response

def get_opportunities_for_children() -> OpportunityChildrenResponse:
    opportunity_dict = defaultdict(list[Opportunity])
    parents = ParentOpportunity.objects.select_related('sport').prefetch_related(
        'children',
        'children__sport',
        'children__sportsbook',
    ).all()
    for parent in parents: 
        opportunity_dict[parent.id] = [child for child in parent.children]

    response = OpportunityChildrenResponse.data_class_from_models(parents, opportunity_dict)
    return response
    
def get_opportunities_for_links() -> OpportunityLinkResponse:
    parents = ParentOpportunity.objects.select_related('sport').all()
    response = OpportunityLinkResponse.data_class_from_models(parents)
    return response    

# TODO: add ngrok
# TODO: users and JWT authorization
# TODO: after some time too many clients error is raised