from queue import Queue
import threading
from database.models import Sportsbook, Sport
from database.enums import Command
from database.Scrapes.scrape_service import ScrapeService

def scrape_fn(event: threading.Event, import_queue: Queue, send_all_event: threading.Event):
    print('Scraping...')    
    sportsbooks = list(Sportsbook.objects.filter(selected=True).all())
    sports = list(Sport.objects.filter(selected=True).all()) 
    """
        We send only these commands to following queues:
            - REFRESH -> if we want to trigger new iteration of scarping data for selected matches from all selected sportsbooks
            - IMPORT -> if we want to trigger import of all data from all selected sportsbooks
    """
    command_queues = {sportsbook.pk: Queue(maxsize=2) for sportsbook in sportsbooks}
    number_of_sbs = len(sportsbooks)
    result_queue = Queue(maxsize=2 * number_of_sbs)

    # starting threads for scraping sportsbooks data for selected matches, grouping data and importing data across all sportsbooks
    service = ScrapeService(sports, event, send_all_event, command_queues, result_queue, import_queue, number_of_sbs)
    driver_threads = [ threading.Thread(target= service.get_sportsbook_data, args = (sportsbook,)) for sportsbook in sportsbooks ]  
    group_results_thread = threading.Thread(target= service.group_results)    
    import_thread = threading.Thread(target= service.import_fn)    

    for thread in driver_threads:
        thread.start()
    group_results_thread.start()
    import_thread.start()

    # put first REFRESH command to queue, to start the loop 
    for queue in command_queues.values():
        queue.put(Command.REFRESH)

    # wait for all threads to finish    
    for thread in driver_threads:
        thread.join()
    group_results_thread.join()
    import_thread.join()
    print('Main function done.')    
