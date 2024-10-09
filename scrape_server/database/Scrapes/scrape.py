from queue import Queue
from ..models import Sportsbook, Sport
import threading
from .scrape_service import get_sportsbook_data, group_results, import_fn
from ..enums import Command

def scrape_fn(event: threading.Event, import_queue: Queue, send_all_event: threading.Event):
    print('Scraping...')    
    sportsbooks = Sportsbook.objects.filter(selected=True).all()
    sports = Sport.objects.filter(selected=True).all()
    command_queues= {} 
    for sportsbook in sportsbooks: 
        command_queues[sportsbook.pk] = Queue(maxsize=2)
    number_of_sbs = sportsbooks.count()
    result_queue = Queue(maxsize=2*number_of_sbs)
    driver_threads = [threading.Thread(target= get_sportsbook_data, args = (command_queues[sportsbook.pk], result_queue, event, sportsbook, sports)) for sportsbook in sportsbooks]  
    group_results_thread = threading.Thread(target= group_results, args = (command_queues, result_queue, event, number_of_sbs, send_all_event))    
    import_thread = threading.Thread(target= import_fn, args = (command_queues, import_queue, event))    
    for thread in driver_threads:
        thread.start()
    group_results_thread.start()
    import_thread.start()
    for _, queue in command_queues.items():
        queue.put(Command.REFRESH) 
    for thread in driver_threads:
            thread.join()
    group_results_thread.join()
    import_thread.join()
    print('Main function done.')    
