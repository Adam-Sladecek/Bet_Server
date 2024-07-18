import queue
from django.db import close_old_connections
from .SportsBooks.nike import NikeScraper
# from .SportsBooks.tipsport import TipsportScraper
import threading
# from .scripts import link_all_events, get_arbitrage_odds, update_odds, link_odds, send_data_to_clients, get_all_arbitrage_bets, broadcast_error
import asyncio
from .SportsBooks.scraper import Scraper
from ..enums import DataType, TaskState
from .scripts import broadcast_data
from ..models import Sportsbook
from .dataclass_models import RequestModel

def get_sportsbook_data(result_queue: queue.Queue, event: threading.Event, sportsbook: Sportsbook): 
    try:
        while True:
            if event.is_set():
                break
            if f:
                asyncio.run(asyncio.sleep(1))
                continue
            events = Event.objects.select_related('sport', 'sportsbook').prefetch_related('odds', 'children').filter(is_default=True, selected=True).all()
            scraper: Scraper = scrapers[request.sportsbook_name](request)
            print(f"Fetching {request.sport_name} data from {request.sportsbook_name}.")
            odds_to_create, odds_to_update, odds_to_delete = scraper.get_data()
            if odds_to_create is not None:
                update_odds(odds_to_create, odds_to_update, odds_to_delete, request.sport_id, request.sportsbook_id)
            result_queue.put(request)
        print('Done handling drivers.')  
    except Exception as ex:
        print('Exception: ' + str(ex))
        event.set()
        broadcast_data(DataType.ERROR, str(ex))

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
                result_dictionary[request.sport_id] = []
                       
        print('Getting results done.')  
    except Exception as ex:
        print('Exception: ' + str(ex))
        event.set()
        broadcast_data(DataType.ERROR, str(ex))

def scrape_sport(sport_id: int, sport_name: str, requests, scrape_queue: queue.Queue): 
    link_all_events(sport_id)
    link_odds(sport_id)
    get_arbitrage_odds(sport_id)
    arb_bets = get_all_arbitrage_bets()
    asyncio.run(send_data_to_clients(arb_bets))
    if requests is not None and scrape_queue is not None:
        for req in requests:
            scrape_queue.put(req, block=True, timeout=None)
        close_old_connections()
        print(f"End of scrape {sport_name}")    

def import_data(requests: list[RequestModel]):
    scraper = ger_scraper(requests)
    scraper.import_all_data()
    asyncio.run(broadcast_data(DataType.IMPORTRUNNING, TaskState.CLOSED))

def ger_scraper(requests: list[RequestModel]) -> Scraper: 
    scrapers = {
        'Pinacle': 1,
        'Doxxbet' : 1, 
        'Ifortuna': 1,
        'Tipos': 1,
        'Nike': NikeScraper,
        # 'Tipsport': TipsportScraper 
        'Tipsport': 1 
    }
    return scrapers[requests[0].sportsbook_name](requests)
