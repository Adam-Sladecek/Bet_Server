import threading
import asyncio
import queue
from database.models import Sportsbook, Sport
from database.enums import DataType, TaskState, Command
from database.Scrapes.SportsBooks.nike import NikeScraper
from database.Scrapes.SportsBooks.tipsport import TipsportScraper
from database.Scrapes.SportsBooks.NotUsed.pinnacle import PinnacleScraper
from database.Scrapes.SportsBooks.ifortuna import IfortunaScraper
from database.Scrapes.SportsBooks.betfair import BetfairScraper
from database.Scrapes.SportsBooks.NotUsed.ps3838 import PS3838Scraper
from database.Scrapes.SportsBooks.scraper import Scraper
from database.Scrapes.helpers import ScrapeHelper

class ScrapeService: 
    def __init__(self, sports: list[Sport], event: threading.Event, send_all_event: threading.Event, 
        command_queues: dict[int, queue.Queue], result_queue: queue.Queue, import_queue: queue.Queue, number_of_sbs: int) -> None:
        self.sports = sports
        self.event = event
        self.send_all_event = send_all_event
        self.all_command_queues = command_queues
        self.result_queue = result_queue
        self.import_queue = import_queue
        self.number_of_sbs = number_of_sbs
        self.scrape_helper = ScrapeHelper()
        self.scrape_helper.clear_unused_events()
        self.scrape_helper.unselect_events()

    def get_sportsbook_data(self, sportsbook: Sportsbook) -> None: 
        try:
            command_queue = self.all_command_queues[sportsbook.pk]
            scraperClass = self.get_scraper_class(sportsbook)
            with scraperClass(sportsbook, self.sports) as scraper:
                self.process_commands(scraper, command_queue)
            print('Done handling drivers.')  
        except Exception as ex:
            self.handle_exception(ex)

    def process_commands(self, scraper: Scraper, command_queue: queue.Queue) -> None:
        while not self.event.is_set():
            try:
                command: Command = command_queue.get(timeout=1)
                self.execute_command(scraper, command)
            except queue.Empty:
                continue

    def execute_command(self, scraper: Scraper, command: Command) -> None:
        if command == Command.IMPORT:
            scraper.import_events()
        else:    
            scraper.refresh_prices()
        self.result_queue.put(command)

    def group_results(self) -> None: 
        try:
            result_count = self.initialize_result_dictionary()
            while not self.event.is_set():
                try:
                    command: Command = self.result_queue.get(timeout=1)
                    result_count[command.value] +=1
                    if result_count[command.value] == self.number_of_sbs:
                        self.handle_group_result(command, result_count)
                except queue.Empty:
                    continue
            print('Getting results done.')  
        except Exception as ex:
            self.handle_exception(ex)

    def handle_group_result(self, command: Command, result_count: dict) -> None:
        if command == Command.REFRESH: 
            self.scrape_helper.link_prices()
            is_set = self.send_all_event.is_set()
            self.scrape_helper.send_updated_events(is_set)
            if is_set: 
                self.send_all_event.clear()
            asyncio.run(asyncio.sleep(5))
        else:
            self.scrape_helper.link_events()
            asyncio.run(self.scrape_helper.broadcast_data(DataType.IMPORTRUNNING, TaskState.CLOSED))
            print('Import done.')
        result_count[command.value] = 0
        self.refresh_all_command_queues()

    def refresh_all_command_queues(self):
        for sb_queue in self.all_command_queues.values():
            sb_queue.put(Command.REFRESH)

    def initialize_result_dictionary(self) -> dict:
        return {Command.REFRESH.value: 0, Command.IMPORT.value: 0}
    
    def import_fn(self) -> None:
        try:
            while not self.event.is_set():
                try:
                    command: Command = self.import_queue.get(timeout=1)
                    self.start_import(command)
                except queue.Empty:
                    continue
            print(f"Import thread finished.")   
        except Exception as ex:
            self.handle_exception(ex)

    def start_import(self, command: Command) -> None:
        print('Starting import.')
        for command_queue in self.all_command_queues.values(): 
            command_queue.put(command, block=True, timeout=None)

    def get_scraper_class(self, sportsbook: Sportsbook) -> Scraper: 
        scrapers: dict[str, Scraper]  = {
            'Nike': NikeScraper,
            'Tipsport': TipsportScraper,
            'Pinnacle': PinnacleScraper,
            'Ifortuna': IfortunaScraper,
            'PS3838': PS3838Scraper,
            'Betfair': BetfairScraper,
        }
        return scrapers[sportsbook.name]

    def handle_exception(self, ex: Exception) -> None:
        print('Exception: ' + str(ex))
        self.event.set()
        self.scrape_helper.broadcast_data(DataType.ERROR, str(ex))