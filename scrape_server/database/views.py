import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Opportunity, OpportunityToBeLinked, Sportsbook, Sport, OpportunityLink
# from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from .Scrapes.dataclass_models import ConfigResponse, Config, OpportunityLinkResponseDict, UnassignedOpportunityResponse, UnassignedOpportunity

@require_GET
def get_config(request):
    sportsbooks = Sportsbook.objects.order_by('id').all()
    sports = Sport.objects.order_by('id').all()
    response = ConfigResponse(
        sports= [Config(sport.pk, sport.name, sport.selected) for sport in sports],
        sportsBooks= [Config(sportsbook.pk, sportsbook.name, sportsbook.selected) for sportsbook in sportsbooks]
    )

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

        sb_ids = [sb.id for sb in data.sportsBooks]
        all_sbs = Sportsbook.objects.all()
        for sb in all_sbs:
            sb.selected = sb.pk in sb_ids

        Sport.objects.bulk_update(all_sports, ['selected'])
        Sportsbook.objects.bulk_update(all_sbs, ['selected'])
        return JsonResponse({'message': 'Configuration saved.'}, status=200)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)

@require_GET
def get_opportunities_to_link(request):
    sportsbooks = Sportsbook.objects.prefetch_related(
        'opportunities_to_be_linked',
        'opportunities_to_be_linked__opportunity',
    ).all()
    result = UnassignedOpportunityResponse(data={sportsbook.name: [] for sportsbook in sportsbooks})
    for sb in sportsbooks:
        for opp_tbl in sb.opportunities_to_be_linked.all():
            opp = opp_tbl.opportunity
            vals = [opp.pk, opp_tbl.pk, opp.opp_description, opp.tip_type, opp.opp_number, opp.market_id, opp.bet_order, opp.sport.name, opp.sportsbook.name]
            result.data[sb.name].append(UnassignedOpportunity(*vals))
    return JsonResponse(result.dict, status=200)

@csrf_exempt
@require_POST
def set_opportunity_link(request):
    try: 
        opportunities = UnassignedOpportunity.dict_to_UO_list(json.loads(request.body))
        ids_to_delete = [opp.opportunity_tbl_id for opp in opportunities]
        first_opp = Opportunity.objects.filter(id=opportunities[0].opportunity_id).first()
        second_opp = Opportunity.objects.filter(id=opportunities[1].opportunity_id).first()
        OpportunityToBeLinked.objects.filter(id__in=ids_to_delete).delete()
        OpportunityLink.objects.create(first_opportunity=first_opp, second_opportunity=second_opp)
        return JsonResponse({'message': 'Opportunity link saved.'}, status=200)  
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=400)   

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

# TODO: add ngrok
# TODO: users and JWT authorization
# TODO: after some time too many clients error is raised