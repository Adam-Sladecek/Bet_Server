from abc import ABC, abstractmethod
import json
import aiohttp 
import asyncio
from datetime import datetime
from ...models import Sport, Sportsbook, Event, Odd
from ...enums import Movement
from ..helpers import OddHelper, EventHelper
from ..dataclass_models import EventModel, OddModel

class Scraper(ABC):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        self.sportsbook = sportsbook
        self.sports = [sport for sport in sports]
        self.odd_helper = OddHelper(sportsbook)
        self.event_helper = EventHelper(sportsbook)
        self.get_driver()

    @abstractmethod
    def get_driver(self):
        pass

    @abstractmethod
    def close_driver(self):
        pass

    @abstractmethod
    async def gather_events(self, sports: list[Sport]):
        pass

    @abstractmethod
    async def gather_odds(self, events):
        pass

    @abstractmethod
    def map_events(self, data) -> list[EventModel]:
        pass

    @abstractmethod
    def map_odds(self, data) -> tuple[list[OddModel], list[Odd]]:
        pass

    @abstractmethod
    def map_events_selected(self, events: list[Event], event_response) -> tuple[list[Event], list[Event]]:
        pass

    @abstractmethod
    def map_odds_selected(self, events: list[Event], odds_response: list[object]) -> list[Odd]:
        pass

    def get_data(self):
        try:
            events, sport_ids = self.event_helper.get_selected_events()
            if len(events) == 0: 
                return
            sports = [sport for sport in self.sports if sport.pk in sport_ids]
            loop = self.get_loop()
            event_response = loop.run_until_complete(self.gather_events(sports))
            events_to_update, events_to_delete = self.map_events_selected(events, event_response)
            self.event_helper.update_selected_events(events_to_update, events_to_delete)
            events = [event for event in events if event.pk is not None]
            odds_response = loop.run_until_complete(self.gather_odds(events))
            odds_to_update = self.map_odds_selected(events, odds_response)
            self.odd_helper.update_selected_odds(odds_to_update)

        except Exception as ex:
            print(f"Get data in {self.sportsbook.name} failed. Exception: {str(ex)}.")

    def import_all_data(self):
        try:
            loop = self.get_loop()
            event_response = loop.run_until_complete(self.gather_events(self.sports))
            events = self.map_events(event_response)
            self.event_helper.update_events(events)    
            odds_response = loop.run_until_complete(self.gather_odds(events))
            odds_to_create, odds_to_update = self.map_odds(odds_response)
            self.odd_helper.update_odds(odds_to_create, odds_to_update)

        except Exception as ex:
            print(f"Import in {self.sportsbook.name} failed. Exception: {str(ex)}.")  

    def get_loop(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
        
    async def gather_data(self, data: dict[int, str], headers: object) -> dict[int, object]:
        async with aiohttp.ClientSession() as session:
            tasks = [asyncio.create_task(self.fetch_data(session, url, sport_id, headers)) for sport_id, url in data.items()]
            array_data = await asyncio.gather(*tasks)

            return {sport_id: result for sport_id, result in array_data}

    async def fetch_data(self, session: aiohttp.ClientSession, url: str, sport_id: int, headers: object) -> tuple[int, object]:
        async with session.get(url, headers=headers) as resp:
            try:
                result = await resp.json() 
                return (sport_id, result)
            except Exception as ex:
                print(f'Exception in fetch_data {self.sportsbook.name}: {str(ex)}')
                return (sport_id, None)
        
    async def get(self, url: str, headers: object, params: object) -> object:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                try:
                    return await resp.json()  
                except: 
                    return None
                
    def convert_timestamp_to_time_string(self, timestamp_ms: int) -> str:
        timestamp_time = datetime.fromtimestamp(timestamp_ms / 1000)
        time_difference = datetime.now() - timestamp_time
        total_seconds = int(time_difference.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02}'"
    
    def convert_seconds_to_time_string(self, seconds) -> str:
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02}'"
    
    def get_movement(self, old_odds: float, new_odds: float) -> int: 
        old_odds = float(old_odds)
        if new_odds > old_odds: 
            return Movement.UP.value
        elif new_odds < old_odds: 
            return Movement.DOWN.value    
        return Movement.NONE.value

    def replace_by_tokens(self, text: str, replace_pairs: list[tuple[str, str]]) -> str:
        for str_to_replace, replace_tkn in replace_pairs:
            text = text.replace(str_to_replace, replace_tkn)
            # Remove spaces from the string to replace
            new_str_to_replace = str_to_replace.replace(' ', '')
            text = text.replace(new_str_to_replace, replace_tkn)
        return text    