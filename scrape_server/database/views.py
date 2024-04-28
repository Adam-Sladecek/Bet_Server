import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Sportsbook, Sport
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from .Scrapes.dataclass_models import ConfigResponse, Config

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

# TODO: add sockets and ngrok
# TODO: add test and store testing data
# TODO: users and JWT authorization