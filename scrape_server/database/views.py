from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Event, Sportsbook, Sport

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
    
# TODO: add sockets and ngrok
# TODO: add test and store testing data
# TODO: users and JWT authorization