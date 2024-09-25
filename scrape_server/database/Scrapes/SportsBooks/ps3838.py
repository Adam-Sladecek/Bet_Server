import asyncio
from ..dataclass_models import EventModel, OddModel
from ..scripts import get_existing_odds
from ...models import Odd, Event, Sport, Sportsbook, SportsbookMarket
from .scraper import Scraper

class PS3838Scraper(Scraper):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        super().__init__(sportsbook, sports)
        self.headers = {
            'Content-Type': 'application/json', 
            'Accept': 'application/json',
            'Authorization': 'Basic QklBMDAwMzFGNDpCcmVzdG92YW55MTIz'
        }
        asyncio.run(self.get_labels())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_driver(self):
        return None
    
    def close_driver(self):
        pass
    
    async def get_labels(self): 
        pass

    async def gather_events(self, sports: list[Sport]):
        pass

    async def gather_odds(self, events):
        pass
    
    def get_sportids(self) -> dict[int, int]: 
        sport_ids = {
            29: 1, #socker
            19: 2, #hokej
            33: 3, #tenis
            4: 4, #basketbal
            18: 5, #handball
            34: 6, #volejbal
            32: 7, #stolny tenis
            6: 8, # box
        }
        
        return sport_ids

    def map_events(self, data: dict[int, list]) -> list[EventModel]:
        pass
    
    def map_odds(self, data: dict[tuple[int, int], list[object]]) -> tuple[list[OddModel], list[Odd]]:
        pass      

    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        pass
    
    def map_odds_selected(self, events: list[Event], odds_response: dict[int, list[object]]) -> list[Odd]:
        pass