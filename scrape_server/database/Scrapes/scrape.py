from queue import Queue
from database.models import Sportsbook, Sport
import threading
from .scrape_service import get_sportsbook_data, group_results, import_job
from .scrape_service import import_data
from .dataclass_models import RequestModel

def scrape_fn(event: threading.Event):
    sportsbooks = Sportsbook.objects.filter(selected=True).all()
    result_queue = Queue(maxsize=sportsbooks.count())
    driver_threads = [threading.Thread(target = get_sportsbook_data, args = (result_queue, event, sportsbook)) for sportsbook in sportsbooks]  
    group_results_thread = threading.Thread(target = group_results, args = (result_queue, event))    
    for thread in driver_threads:
        thread.start()
    group_results_thread.start()
    for sport in sports: 
        for sportsbook in sportsbooks:
            if sport.sport_type_id == 2 and sportsbook.name == 'Tipos':
                url_parts = getattr(sportsbook, sport.url).split('?')
                url = f'{url_parts[0]}?gameId=20&{url_parts[1]}'
                scrape_queue.put(RequestModel(sport_name = sport.name, sportsbook_id = sportsbook.id, sportsbook_name = sportsbook.name, sport_id = sport.id, sport_type_id = sport.sport_type_id, url = url, is_tipos_more=True), block=True, timeout=None)
            scrape_queue.put(RequestModel(sport_name = sport.name, sportsbook_id = sportsbook.id, sportsbook_name = sportsbook.name, sport_id = sport.id, sport_type_id = sport.sport_type_id, url = getattr(sportsbook, sport.url), is_tipos_more=False), block=True, timeout=None)
    for thread in driver_threads:
            thread.join()
    group_results_thread.join()
    print('Main function done.')    
    return None

def import_job():
    print('Starting import.')
    sportsbooks = Sportsbook.objects.filter(selected=True).all()
    sports = Sport.objects.filter(selected=True).all()
    request_lists: list[list[RequestModel]] = []
    for sb in sportsbooks:
        request_lists.append(RequestModel.dataclass_list_from_models(sb, sports))
    threads = [threading.Thread(target = import_data, args = (requests,)) for requests in request_lists]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print('Import done.') 