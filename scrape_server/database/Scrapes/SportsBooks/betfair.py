import json
from datetime import datetime
from typing import Optional
import aiohttp
from ...models import Sport, Sportsbook, Event, Odd, SportsbookMarket
from ..helpers import OddHelper, EventHelper
from ..dataclass_models import EventModel, OddModel
from .scraper import Scraper

class BetfairScraper(Scraper):
    BASE_URL = "https://api.betfair.com/exchange/betting/rest/v1.0/"
    
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        super().__init__(sportsbook, sports)
        self.session_token = None
        self.app_key = "YOUR_APP_KEY"  # Get from Betfair Developer Program
        self.markets = [sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()]
        
    def get_driver(self):
        # Not needed for REST API
        pass

    def close_driver(self):
        # Not needed for REST API
        pass

    async def authenticate(self):
        # You'll need to implement authentication using your Betfair credentials
        # Store session token in self.session_token
        pass

    def get_headers(self):
        return {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'content-type': 'application/json'
        }

    def get_sportids(self) -> dict[str, int]: 
        return {
            '1': 1, #socker
            '7524': 2, #hokej
            '2': 3, #tenis
            '7522': 4, #basketbal
            '468328': 5, #handball
            '998917': 6, #volejbal
            '': 7, #stolny tenis
            '6': 8, # box
        }

    async def gather_events(self, sports: list[Sport]):
        if not self.session_token:
            await self.authenticate()

        sport_id_map = {v: k for k, v in self.get_sportids().items()}
        
        params = {
            "filter": {
                "eventTypeIds": [sport_id_map[sport.pk] for sport in sports],
                "marketTypeCodes": self.markets,
                "inPlayOnly": True
            }
        }
            
        url = f"{self.BASE_URL}/listEvents/"
        response = await self.get(url, self.get_headers(), params)

        return response

    async def gather_odds(self, events: list[EventModel]):
        if not self.session_token:
            await self.authenticate()

        market_ids = [event.event_id for event in events]
        params = {
            "marketIds": market_ids,
            "priceProjection": {
                "priceData": ["EX_BEST_OFFERS"]
            }
        }
        
        url = f"{self.BASE_URL}/listMarketBook/"
        return await self.get(url, self.get_headers(), params)

    def map_events(self, data) -> list[EventModel]:
        events = []
        for sport_id, sport_data in data.items():
            for event in sport_data:
                events.append(EventModel(
                    event_id=event['marketId'],
                    league_id=event.get('competition', {}).get('id', ''),
                    time=self.parse_event_time(event.get('marketStartTime')),
                    home=event['runners'][0]['runnerName'],
                    away=event['runners'][1]['runnerName'],
                    selected=True,
                    sportsbook_id=self.sportsbook.pk,
                    sport_id=sport_id
                ))
        return events

    def map_odds(self, data) -> tuple[list[OddModel], list[Odd]]:
        odds_to_create = []
        odds_to_update = []
        existing_odds = self.odd_helper.get_existing_odds()

        for market in data:
            market_id = market['marketId']
            for runner in market['runners']:
                best_back = runner.get('ex', {}).get('availableToBack', [{}])[0]
                best_lay = runner.get('ex', {}).get('availableToLay', [{}])[0]
                
                if best_back and best_lay:
                    odd_id = f"{market_id}_{runner['selectionId']}"
                    odd_value = (float(best_back['price']) + float(best_lay['price'])) / 2
                    
                    if market_id in existing_odds and odd_id in existing_odds[market_id]:
                        existing_odd = existing_odds[market_id][odd_id]
                        existing_odd.odd = odd_value
                        existing_odd.movement = self.get_movement(existing_odd.odd, odd_value)
                        odds_to_update.append(existing_odd)
                    else:
                        odds_to_create.append(OddModel(
                            odd_id=odd_id,
                            event_id=market_id,
                            code=str(runner['selectionId']),
                            description=runner['description'],
                            odd=odd_value,
                            movement=0,
                            selected=True,
                            locked=False,
                            market_id=market_id
                        ))

        return odds_to_create, odds_to_update

    def parse_event_time(self, time_str: Optional[str]) -> str:
        if not time_str:
            return "0:00'"
        try:
            event_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            time_diff = datetime.now() - event_time
            total_seconds = int(time_diff.total_seconds())
            return self.convert_seconds_to_time_string(total_seconds)
        except:
            return "0:00'" 