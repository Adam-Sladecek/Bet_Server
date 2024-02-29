import queue
from .nike import nike_getData
from .tipsport import tipsport_getData
import asyncio
import threading
from .scripts import link_all_events, get_arbitrage_odds, update_events, update_odds, link_odds

def get_sportsbook_data(scrape_queue: queue.Queue, result_queue: queue.Queue, event: threading.Event): 
    try:
        targets = {
            'Doxxbet' : 1, 
            'Ifortuna': 1,
            'Tipos': 1,
            'Betfair': 1,
            'Nike': nike_getData,
            'Tipsport': tipsport_getData 
        }
        while True:
            if event.is_set():
                break
            try:
                request = scrape_queue.get(timeout=1)
            except queue.Empty:
                # raise
                continue

            args = (request,)
            events, odds = asyncio.run(targets[request.sportsbook_name](*args, test=False))
            if events is not None:
                update_events(events, request.sport_id, request.sportsbook_id)
            if odds is not None:
                update_odds(odds, request.sport_id, request.sportsbook_id)
            result_queue.put(request)
            print(f"Scraping {request.sportsbook_name} finished.")

        print('Done handling drivers.')  
    except Exception as ex:
        event.set()

def group_results(scrape_queue: queue.Queue, result_queue: queue.Queue, event: threading.Event, number_of_sportsbooks: int, tipos_included: bool): 
    try:
        result_dictionary = {}
        while True:
            if event.is_set():
                break
            try:
                request = result_queue.get(timeout=1)
            except queue.Empty:
                continue

            if request.sport_id not in result_dictionary:
                result_dictionary[request.sport_id] = []
            result_dictionary[request.sport_id].append(request)    
            neccessaryCount = number_of_sportsbooks + 1 if (tipos_included and request.sport_type_id == 2) else number_of_sportsbooks
            if len(result_dictionary[request.sport_id]) == neccessaryCount:
                print("Scraping", request.sport_name)
                calc_thread = threading.Thread(target = scrape_sport, args = (request.sport_id, request.sport_name, result_dictionary[request.sport_id], scrape_queue))
                calc_thread.daemon = True
                calc_thread.start()
                # for req in result_dictionary[request.sport_id]:
                #     scrape_queue.put(req, block=True, timeout=None)
                result_dictionary[request.sport_id] = []
                       
        print('Getting results done.')  
    except Exception as ex:
        event.set()

def scrape_sport(sport_id: int, sport_name: str, requests, scrape_queue: queue.Queue): 
    link_all_events(sport_id)
    link_odds(sport_id)
    get_arbitrage_odds(sport_id)
    for req in requests:
        scrape_queue.put(req, block=True, timeout=None)
    print(f"End of scrape {sport_name}")    
