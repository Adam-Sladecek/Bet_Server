from queue import Queue
import threading
from database.models import Sportsbook, Sport
from database.enums import Command
from database.Scrapes.scrape_service import get_sportsbook_data, group_results, import_fn

def scrape_fn(event: threading.Event, import_queue: Queue, send_all_event: threading.Event):
    print('Scraping...')    
    sportsbooks = Sportsbook.objects.filter(selected=True).all()
    sports = Sport.objects.filter(selected=True).all()

    """
        We send only these commands to following queues: 
            - REFRESH -> if we want to trigger new iteration of scarping data for selected matches from all selected sportsbooks
            - IMPORT -> if we want to trigger import of all data from all selected sportsbooks
    """
    command_queues= {}
    for sportsbook in sportsbooks: 
        command_queues[sportsbook.pk] = Queue(maxsize=2)
    number_of_sbs = sportsbooks.count()
    result_queue = Queue(maxsize=2*number_of_sbs)

    # starting threads for scraping sportsbooks data for selected matches, grouping data and importing data across all sportsbooks
    driver_threads = [
        threading.Thread(target= get_sportsbook_data, args = (command_queues[sportsbook.pk], result_queue, event, sportsbook, sports))
        for sportsbook in sportsbooks
    ]  
    group_results_thread = threading.Thread(target= group_results, args = (command_queues, result_queue, event, number_of_sbs, send_all_event))    
    import_thread = threading.Thread(target= import_fn, args = (command_queues, import_queue, event))    
    for thread in driver_threads:
        thread.start()
    group_results_thread.start()
    import_thread.start()

    # put first REFRESH command to queue, to start the loop 
    for _, queue in command_queues.items():
        queue.put(Command.REFRESH) 

    # wait for all threads to finish    
    for thread in driver_threads:
            thread.join()
    group_results_thread.join()
    import_thread.join()
    print('Main function done.')    
