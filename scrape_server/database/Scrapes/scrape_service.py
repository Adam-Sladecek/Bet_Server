import threading
import asyncio
import queue
from database.models import Sportsbook, Sport
from database.enums import DataType, TaskState, Command
from database.Scrapes.SportsBooks.nike import NikeScraper
from database.Scrapes.SportsBooks.tipsport import TipsportScraper
from database.Scrapes.SportsBooks.pinnacle import PinnacleScraper
from database.Scrapes.SportsBooks.ifortuna import IfortunaScraper
from database.Scrapes.SportsBooks.ps3838 import PS3838Scraper
from database.Scrapes.SportsBooks.scraper import Scraper
from database.Scrapes.scripts import broadcast_data, send_updated_events, clear_unused_events, link_all_events, link_odds

class ScrapeService: 
    def __init__(self, sports: list[Sport], event: threading.Event, send_all_event: threading.Event, 
                 command_queues: dict[int, queue.Queue], result_queue: queue.Queue, import_queue: queue.Queue, number_of_sbs: int):
        self.sports = sports
        self.event = event
        self.send_all_event = send_all_event
        self.all_command_queues = command_queues
        self.result_queue = result_queue
        self.import_queue = import_queue
        self.number_of_sbs = number_of_sbs
            
    def get_sportsbook_data(self, sportsbook: Sportsbook): 
        try:
            command_queue = self.all_command_queues[sportsbook.pk]
            scraperClass = self.get_scraper_class(sportsbook)
            with scraperClass(sportsbook, self.sports) as s:
                while True:
                    if self.event.is_set():
                        break
                    try:
                        command: Command = command_queue.get(timeout=1)
                    except queue.Empty:
                        continue

                    if command == Command.IMPORT:
                        s.import_all_data()
                    else:    
                        s.get_data()

                    self.result_queue.put(command)
                s.close_driver()    
            print('Done handling drivers.')  
        except Exception as ex:
            print('Exception in get_sportsbook_data: ' + str(ex))
            try:
                s.close_driver()  
            except: pass
            self.event.set()
            broadcast_data(DataType.ERROR, str(ex))

    def group_results(self): 
        try:
            result_dictionary = {}
            result_dictionary[Command.REFRESH.value] = 0
            result_dictionary[Command.IMPORT.value] = 0
            while True:
                if self.event.is_set():
                    break
                try:
                    command: Command = self.result_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                result_dictionary[command.value] +=1
                if result_dictionary[command.value] == self.number_of_sbs:
                    if command == Command.REFRESH: 
                        is_set = self.send_all_event.is_set()
                        send_updated_events(is_set)
                        if is_set: self.send_all_event.clear()
                        asyncio.run(asyncio.sleep(5))
                    else:
                        self.link_events_and_odds()
                        asyncio.run(broadcast_data(DataType.IMPORTRUNNING, TaskState.CLOSED))
                        print('Import done.') 
                    result_dictionary[command.value] = 0
                    for _, sb_queue in self.all_command_queues.items():
                        sb_queue.put(Command.REFRESH) 
                        
            print('Getting results done.')  
        except Exception as ex:
            print('Exception in group_results: ' + str(ex))
            self.event.set()
            broadcast_data(DataType.ERROR, str(ex))

    def import_fn(self):
        try:
            while True:
                if self.event.is_set():
                    break
                try:
                    command: Command = self.import_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                print('Starting import.')
                for _, command_queue in self.all_command_queues.items(): 
                    command_queue.put(command, block=True, timeout=None)

            print(f"Import thread finished.")   
        except Exception as ex:
            print('Exception in import_fn: ' + str(ex))
            self.event.set()
            broadcast_data(DataType.ERROR, str(ex))

    def link_events_and_odds(self): 
        clear_unused_events()
        link_all_events()
        link_odds()

    def get_scraper_class(self, sportsbook: Sportsbook) -> Scraper: 
        scrapers: dict[str, Scraper]  = {
            'Nike': NikeScraper,
            'Tipsport': TipsportScraper,
            'Pinnacle': PinnacleScraper,
            'Ifortuna': IfortunaScraper,
            'PS3838': PS3838Scraper,
        }
        return scrapers[sportsbook.name]
