import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Opportunity, Sportsbook, Sport, ParentOpportunity
# from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from .Scrapes.dataclass_models import ConfigResponse, ParentOpportunityDataClass, OpportunityDataClass, OpportunityFactoryResponse
from django.db import transaction

@require_GET
def get_config(request):
    sports = Sport.objects.order_by('id').all()
    sportsbooks = Sportsbook.objects.order_by('id').all()
    response = ConfigResponse.dataclass_from_models(sports, sportsbooks)
    return JsonResponse(response.dict, status=200)

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
    response = opportunities_for_factory()
    return JsonResponse(response.dict, status=200)

@csrf_exempt
@require_POST
def link_parent_opportunity(request):
    try: 
        parent_opportunity_dataclasses = ParentOpportunityDataClass.dict_to_dataclass_list(json.loads(request.body))
        first_parent = ParentOpportunity.objects.get(parent_opportunity_dataclasses[0].id)
        second_parent = ParentOpportunity.objects.get(parent_opportunity_dataclasses[1].id)
        with transaction.atomic():
            first_parent.link_with(second_parent)

        response = opportunities_for_factory()

        return JsonResponse(response.dict, status=200)  
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)   

@csrf_exempt
@require_POST
def add_parent_opportunity(request):
    opportunity_dataclass = OpportunityDataClass.dict_to_dataclass(json.loads(request.body))
    opportunity = Opportunity.objects.get(opportunity_dataclass.id)
    


@csrf_exempt
@require_POST
def add_child_to_parent_opportunity(request):

@require_GET
def get_opportunity_links(request):
    opportunity_links = OpportunityLink.objects.select_related(
        'first_opportunity',
        'second_opportunity',
        'first_opportunity__sportsbook',
        'second_opportunity__sportsbook',
        'first_opportunity__sport',
        'second_opportunity__sport',
    ).all()
    result = OpportunityLinkResponseDict.opp_link_to_OL_dict(opportunity_links)
    return JsonResponse(result.dict, status=200)      
    
@csrf_exempt
def delete_opportunity_link(request, pk):
    opportunity_link = OpportunityLink.objects.filter(pk=pk).first()
    OpportunityToBeLinked.objects.create(opportunity=opportunity_link.first_opportunity, target_sportsbook=opportunity_link.second_opportunity.sportsbook)
    OpportunityToBeLinked.objects.create(opportunity=opportunity_link.second_opportunity, target_sportsbook=opportunity_link.first_opportunity.sportsbook)
    opportunity_link.delete()
    return JsonResponse({'message': 'Opportunity link deleted.'}, status=200)   

def opportunities_for_factory() -> OpportunityFactoryResponse: 
    parents = ParentOpportunity.objects.select_related('sport').all()
    opportunities = Opportunity.objects.select_related('sport', 'sportsbook').filter(has_parent=False).all()
    response = OpportunityFactoryResponse.data_class_from_models(parents, opportunities)
    return response

# TODO: add ngrok
# TODO: users and JWT authorization
# TODO: after some time too many clients error is raised