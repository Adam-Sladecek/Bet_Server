import queue
from django.db import close_old_connections
from .SportsBooks.nike import NikeScraper
# from .SportsBooks.tipsport import TipsportScraper
import threading
# from .scripts import link_all_events, get_arbitrage_odds, update_odds, link_odds, send_data_to_clients, get_all_arbitrage_bets, broadcast_error
import asyncio
from .SportsBooks.scraper import Scraper
from ..enums import DataType, TaskState, Command
from .scripts import broadcast_data
from ..models import Sportsbook, Sport
from collections import defaultdict

def get_sportsbook_data(command_queue: queue.Queue, result_queue: queue.Queue, event: threading.Event, sportsbook: Sportsbook, sports: list[Sport]): 
    try:
        with get_scraper(sportsbook, sports) as scraper:
            while True:
                if event.is_set():
                    break
                try:
                    command: Command = command_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if command == Command.IMPORT:
                    scraper.import_all_data()
                    result_queue.put(command)
                    continue

                print(f"Fetching data from {sportsbook.name}.")
                scraper.get_data()
                result_queue.put(command)
        print('Done handling drivers.')  
    except Exception as ex:
        print('Exception: ' + str(ex))
        event.set()
        broadcast_data(DataType.ERROR, str(ex))

def group_results(command_queues: dict[int, queue.Queue], result_queue: queue.Queue, event: threading.Event, number_of_sbs: int): 
    try:
        result_dictionary = defaultdict[int]
        result_dictionary[Command.REFRESH] = 0
        result_dictionary[Command.IMPORT] = 0
        while True:
            if event.is_set():
                break
            try:
                command = result_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            result_dictionary[command] +=1
            if result_dictionary[command] == number_of_sbs:
                if command == Command.REFRESH: 
                    # send data to clients
                    pass
                else:
                    link_events_and_odds()
                    asyncio.run(broadcast_data(DataType.IMPORTRUNNING, TaskState.CLOSED))
                    print('Import done.') 
                result_dictionary[command] = 0
                for _, sb_queue in command_queues.items():
                    sb_queue.push(Command.REFRESH) 
                       
        print('Getting results done.')  
    except Exception as ex:
        print('Exception: ' + str(ex))
        event.set()
        broadcast_data(DataType.ERROR, str(ex))

def import_fn(command_queues: dict[int, queue.Queue], import_queue: queue.Queue, event: threading.Event):
    try:
        while True:
            if event.is_set():
                break
            try:
                command: Command = import_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            print('Starting import.')
            for _, command_queue in command_queues.items(): 
                command_queue.put(command, block=True, timeout=None)

        print(f"Import thread finished.")   
    except Exception as ex:
        print('Exception: ' + str(ex))
        event.set()
        broadcast_data(DataType.ERROR, str(ex))

def link_events_and_odds(): 
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

def get_scraper(sportsbook: Sportsbook, sports: list[Sport]) -> Scraper: 
    scrapers = {
        'Pinacle': 1,
        'Doxxbet' : 1, 
        'Ifortuna': 1,
        'Tipos': 1,
        'Nike': NikeScraper,
        # 'Tipsport': TipsportScraper 
        'Tipsport': 1 
    }
    return scrapers[sportsbook.name](sportsbook, sports)
