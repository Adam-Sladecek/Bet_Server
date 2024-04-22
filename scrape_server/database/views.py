import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Event, Sportsbook, Sport
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt

@require_GET
def delete_event(request):
    try:
        eventid = request.GET.get('eventid', None)
        Event.objects.get(event_id=int(eventid)).delete()
        return JsonResponse({'success': True}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@require_GET
def get_config(request):
    try:
        sportsbooks = Sportsbook.objects.order_by('id').all()
        sports = Sport.objects.order_by('id').all()
        response = {
            'sportsbooks': [{'id': sportsbook.pk, 'name': sportsbook.name, 'selected': sportsbook.selected} for sportsbook in sportsbooks],
            'sports': [{'id': sport.pk, 'name': sport.name, 'selected': sport.selected} for sport in sports]
        }

        return JsonResponse(response, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)    

# @require_GET
# def get_csrf_token(request):
#     token = get_token(request)
#     return JsonResponse({'csrfToken': token}) 
   
@csrf_exempt
def set_config(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            sports_ids = [sport['id'] for sport in data['sports']]
            all_sports = Sport.objects.all()
            for sport in all_sports:
                if sport.pk in sports_ids:
                    sport.selected = True
                else:
                    sport.selected = False
                sport.save()

            sb_ids = [sb['id'] for sb in data['sportsBooks']]
            all_sbs = Sportsbook.objects.all()
            for sb in all_sbs:
                if sb.pk in sb_ids:
                    sb.selected = True
                else:
                    sb.selected = False
                sb.save()
                
            return JsonResponse({'success': True, 'message': 'Configuration saved.'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return JsonResponse({'error': 'POST method required'}, status=405)



# TODO: add sockets and ngrok
# TODO: add test and store testing data
# TODO: users and JWT authorization