import queue
from django.db import close_old_connections
from .SportsBooks.nike import NikeScraper
from .SportsBooks.tipsport import TipsportScraper
import threading
import asyncio
from .SportsBooks.scraper import Scraper
from ..enums import DataType, TaskState, Command
from .scripts import broadcast_data, send_updated_events, clear_unused_events, link_all_events, link_odds
from ..models import Sportsbook, Sport

def get_sportsbook_data(command_queue: queue.Queue, result_queue: queue.Queue, event: threading.Event, sportsbook: Sportsbook, sports: list[Sport]): 
    try:
        scraper = get_scraper(sportsbook, sports)
        with scraper as s:
            s.get_driver()
            while True:
                if event.is_set():
                    break
                try:
                    command: Command = command_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if command == Command.IMPORT:
                    print(f"Importing data from {sportsbook.name}.")
                    s.import_all_data()
                else:    
                    print(f"Fetching data from {sportsbook.name}.")
                    s.get_data()

                result_queue.put(command)
            s.close_driver()    
        print('Done handling drivers.')  
    except Exception as ex:
        print('Exception in get_sportsbook_data: ' + str(ex))
        scraper.close_driver()  
        event.set()
        broadcast_data(DataType.ERROR, str(ex))

def group_results(command_queues: dict[int, queue.Queue], result_queue: queue.Queue, event: threading.Event, number_of_sbs: int): 
    try:
        result_dictionary = {}
        result_dictionary[Command.REFRESH.value] = 0
        result_dictionary[Command.IMPORT.value] = 0
        while True:
            if event.is_set():
                break
            try:
                command: Command = result_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            result_dictionary[command.value] +=1
            if result_dictionary[command.value] == number_of_sbs:
                if command == Command.REFRESH: 
                    send_updated_events()
                    asyncio.run(asyncio.sleep(4.9))
                else:
                    link_events_and_odds()
                    asyncio.run(broadcast_data(DataType.IMPORTRUNNING, TaskState.CLOSED))
                    print('Import done.') 
                result_dictionary[command.value] = 0
                for _, sb_queue in command_queues.items():
                    sb_queue.put(Command.REFRESH) 
                       
        print('Getting results done.')  
    except Exception as ex:
        print('Exception in group_results: ' + str(ex))
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
        print('Exception in import_fn: ' + str(ex))
        event.set()
        broadcast_data(DataType.ERROR, str(ex))

def link_events_and_odds(): 
    clear_unused_events()
    link_all_events()
    link_odds()
    # close_old_connections()

def get_scraper(sportsbook: Sportsbook, sports: list[Sport]) -> Scraper: 
    scrapers: dict[str, Scraper]  = {
        'Nike': NikeScraper,
        'Tipsport': TipsportScraper
    }
    ScraperClass = scrapers[sportsbook.name]
    return ScraperClass(sportsbook, sports)
