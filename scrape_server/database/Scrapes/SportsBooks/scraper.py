from abc import ABC, abstractmethod
import json
import aiohttp 
import asyncio
from datetime import datetime
from ...models import Sport, Sportsbook, Event, Odd
from ...enums import Movement
from ..scripts import update_events, update_odds, get_selected_events, update_selected_events, update_selected_odds
from ..dataclass_models import EventModel, OddModel

class Scraper(ABC):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        self.sportsbook = sportsbook
        self.sports = [sport for sport in sports]
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
            events, sport_ids = get_selected_events(self.sportsbook)
            if len(events) == 0: return
            sports = [sport for sport in self.sports if sport.pk in sport_ids]
            event_response = asyncio.run(self.gather_events(sports))
            events_to_update, events_to_delete = self.map_events_selected(events, event_response)
            update_selected_events(events_to_update, events_to_delete)
            events = [event for event in events if event.pk is not None]
            odds_response = asyncio.run(self.gather_odds(events))
            odds_to_update = self.map_odds_selected(events, odds_response)
            update_selected_odds(odds_to_update)

        except Exception as ex:
            print(f"Get data in {self.sportsbook.name} failed. Exception: {str(ex)}.")

    def import_all_data(self):
        try:
            event_response = asyncio.run(self.gather_events(self.sports))
            events = self.map_events(event_response)
            update_events(events, self.sportsbook)    
            odds_response = asyncio.run(self.gather_odds(events))
            odds_to_create, odds_to_update = self.map_odds(odds_response)
            update_odds(odds_to_create, odds_to_update, self.sportsbook)

        except Exception as ex:
            print(f"Import in {self.sportsbook.name} failed. Exception: {str(ex)}.")  

    async def gather_data(self, data: dict[int, str], headers: object) -> dict[int, object]:
        async with aiohttp.ClientSession() as session:
            tasks = [asyncio.create_task(self.fetch_data(session, url, sport_id, headers)) for sport_id, url in data.items()]
            array_data = await asyncio.gather(*tasks)

            return {sport_id: result for sport_id, result in array_data}

    async def fetch_data(self, session: aiohttp.ClientSession, url: str, sport_id: int, headers: object) -> tuple[int, object]:
        async with session.get(url, headers=headers) as resp:
            try:
                result = await resp.json() 
            except Exception as ex:
                print(f'Exception in fetch_data {self.sportsbook.name}: {str(ex)}')
                return (sport_id, None)

            return (sport_id, result)
        
    async def get(self, url: str, headers: object) -> object:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                result = await resp.json() 
                return result 
        
    def convert_timestamp_to_time_string(self, timestamp_ms) -> str:
        current_time = datetime.now()
        timestamp_s = timestamp_ms / 1000
        timestamp_time = datetime.fromtimestamp(timestamp_s)
        time_difference = current_time - timestamp_time
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

    async def execute_driver_script(self, url: str): 
        try:
            script = f"""
            var xhr = new XMLHttpRequest();
            xhr.open("GET", "{url}", false);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.onreadystatechange = function () {{
                if (xhr.readyState == 4) {{
                    if (xhr.status == 200) {{
                        window.responseData = xhr.responseText;
                    }} else {{
                        console.error("Request failed with status:", xhr.status);
                        window.responseData = null;
                    }}
                }}
            }};
            xhr.send();
            """
            self.driver.execute_script(script)
            response_data = self.driver.execute_script("return window.responseData;")

            return json.loads(response_data)
        
        except Exception as ex:
            return None

    def replace_by_tokens(self, text: str, replace_pairs: list[tuple[str, str]]) -> str:
        for str_to_replace, replace_tkn in replace_pairs:
            text = text.replace(str_to_replace, replace_tkn)
            space_indexes = [i for i, char in enumerate(str_to_replace) if char == ' ']
            for index in space_indexes:
                string_list = list(str_to_replace)
                string_list[index] = ''
                new_str_to_replace = ''.join(string_list)
                text = text.replace(new_str_to_replace, replace_tkn)
        return text    