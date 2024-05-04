import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Opportunity, OpportunityToBeLinked, Sportsbook, Sport
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from .Scrapes.dataclass_models import ConfigResponse, Config, UnassignedOpportunityResponse, UnassignedOpportunity
from django.db.models import Count

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
            vals = [opp.pk, opp.opp_description, opp.tip_type, opp.opp_number, opp.market_id, opp.bet_order, opp.sport.name, opp.sportsbook.name]
            result.data[sb.name].append(UnassignedOpportunity(*vals))
    return JsonResponse(result.dict, status=200)

# TODO: add ngrok
# TODO: users and JWT authorization