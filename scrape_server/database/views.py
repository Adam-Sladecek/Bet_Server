from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Sportsbook, Sport, Event
from .Scrapes import scrape
import threading

scrape_task_running = False
scrape_event = None
scrape_thread = None

@require_GET
def start_scrape(request):
    try:
        global scrape_task_running, scrape_thread, scrape_event
        print("Starting scrape.")

        sportsbooks = Sportsbook.objects.filter(selected=True)
        sports = Sport.objects.filter(selected=True)

        if not scrape_task_running:
            scrape_event = threading.Event()
            number_of_drivers = 1
            scrape_thread = threading.Thread(target=scrape, args=(sportsbooks, sports, scrape_event, number_of_drivers))
            scrape_thread.start()
            scrape_task_running = True

        print("Scrape started.")
        return JsonResponse({'started': True}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_GET
def end_scrape(request):
    try:
        global scrape_task_running, scrape_event, scrape_thread
        print("Ending scrape.")

        if scrape_task_running:
            scrape_event.set()
            scrape_thread.join()
            scrape_task_running = False

        return JsonResponse({'ended': True}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_GET
def delete_event(request):
    try:
        eventid = request.GET.get('eventid', None)
        Event.objects.get(event_id=int(eventid)).delete()
        return JsonResponse({'success': True}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
# TODO: add sockets
# TODO: users and JWT authorization