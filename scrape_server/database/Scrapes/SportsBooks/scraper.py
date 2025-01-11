from abc import ABC, abstractmethod
import json
import aiohttp 
import asyncio
from database.models import Sport, Sportsbook, Event, Price
from database.enums import Movement
from database.Scrapes.helpers import PriceHelper, EventHelper
from database.Scrapes.dataclass_models import PriceModel

class Scraper(ABC):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        self.sportsbook = sportsbook
        self.sports = [sport for sport in sports]
        self.price_helper = PriceHelper(sportsbook)
        self.event_helper = EventHelper(sportsbook)
        self.get_driver()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close_driver()   

    @abstractmethod
    def get_driver(self) -> None: pass

    @abstractmethod
    def close_driver(self) -> None: pass

    @abstractmethod
    async def gather_events(self, sports: list[Sport]) -> dict[int, object]: pass

    @abstractmethod
    async def gather_prices(self, events: list[Event]) -> dict[int, object]: pass

    @abstractmethod
    def map_events(self, data: dict[int, object]) -> list[Event]: pass

    @abstractmethod
    def map_prices(self, events: list[Event], data: dict[int, object]) -> tuple[list[PriceModel], list[Price]]: pass

    def refresh_odds(self):
        try:
            events = self.event_helper.get_selected_events()
            if len(events) == 0: 
                return
            
            loop = self.get_loop()
            prices_response = loop.run_until_complete(self.gather_prices(events))
            prices_to_create, prices_to_update = self.map_prices(events, prices_response)
            self.price_helper.update_prices(prices_to_create, prices_to_update)
        except Exception as ex:
            print(f"Refresh odds in {self.sportsbook.name} failed. Exception: {str(ex)}.")

    def import_events(self):
        try:
            loop = self.get_loop()
            event_response = loop.run_until_complete(self.gather_events(self.sports))
            events = self.map_events(event_response)
            self.event_helper.update_events(events)    
        except Exception as ex:
            print(f"Import events in {self.sportsbook.name} failed. Exception: {str(ex)}.")  

    def get_loop(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop
    
    async def gather_data(self, url_dict: dict[int, str], headers: object, data_dict: dict[int, object], is_post: bool = False) -> dict[int, object]:
        async with aiohttp.ClientSession() as session:
            request_method = self.post if is_post else self.get
            tasks = [asyncio.create_task(request_method(session, url, headers, data_dict.get(sport_id, {}))) for sport_id, url in url_dict.items()]
            array_data = await asyncio.gather(*tasks)
            
            return {id: result for id, result in zip(url_dict.keys(), array_data)}
        
    async def get(self, session: aiohttp.ClientSession, url: str, headers: object, params: object) -> object:
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    print(f"GET request failed with status {resp.status}: {await resp.text()}")
                    return None
                
                return await resp.json()  
        except Exception as ex:
            print(f"GET request failed: {str(ex)}")
            return None

    async def post(self, session: aiohttp.ClientSession, url: str, headers: object, data: object) -> object:
        try:
            async with session.post(url, headers=headers, data=json.dumps(data)) as resp:
                if resp.status != 200:
                    print(f"POST request failed with status {resp.status}: {await resp.text()}")
                    return None
                
                return await resp.json()
        except Exception as ex:
            print(f"POST request failed: {str(ex)}")
            return None

    def convert_seconds_to_time_string(self, seconds: int) -> str:
        minutes = seconds // 60
        seconds = seconds % 60

        return f"{minutes}:{seconds:02}'"
    
    def get_movement(self, old_odds: float, new_odds: float) -> int: 
        old_odds = float(old_odds)
        if new_odds > old_odds: 
            return Movement.UP.value
        
        if new_odds < old_odds: 
            return Movement.DOWN.value  
          
        return Movement.NONE.value

    def replace_by_tokens(self, text: str, replace_pairs: list[tuple[str, str]]) -> str:
        for str_to_replace, replace_tkn in replace_pairs:
            text = text.replace(str_to_replace, replace_tkn)
            
            # Remove spaces from the string to replace
            new_str_to_replace = str_to_replace.replace(' ', '')
            text = text.replace(new_str_to_replace, replace_tkn)

        return text