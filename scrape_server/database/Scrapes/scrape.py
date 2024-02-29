from queue import Queue
from .dataclass_models import RequestModel
from database.models import Sportsbook, Sport
import threading
from .scrape_service import get_sportsbook_data, group_results

def scrape(sportsbooks: list[Sportsbook], sports: list[Sport], event: threading.Event, number_of_drivers: int):
    if len(sportsbooks) < 2 or len(sports) == 0:
        print('Main function done.') 
        return None
    
    scrape_queue = Queue(maxsize=len(sports) * (len(sportsbooks) + 1))
    result_queue = Queue(maxsize=len(sports) * (len(sportsbooks) + 1))
    driver_threads = [threading.Thread(target = get_sportsbook_data, args = (scrape_queue, result_queue, event)) for _ in range(number_of_drivers)]  
    tipos_included = len([sportsbook for sportsbook in sportsbooks if sportsbook.name == 'Tipos']) > 0
    group_results_thread = threading.Thread(target = group_results, args = (scrape_queue, result_queue, event, len(sportsbooks), tipos_included))    
    for thread in driver_threads:
        thread.start()
    group_results_thread.start()
    for sportsbook in sportsbooks: 
        for sport in sports: 
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