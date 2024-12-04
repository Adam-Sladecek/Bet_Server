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

    def get_data(self):
        try:
            events, sport_ids = self.event_helper.get_selected_events()
            if len(events) == 0: 
                return
            sports = [sport for sport in self.sports if sport.pk in sport_ids]
            loop = self.get_loop()
            event_response = loop.run_until_complete(self.gather_events(sports, [event.event_id for event in events]))
            mapped_events, events_to_delete = self.map_events_selected(events, event_response)
            self.event_helper.update_selected_events(mapped_events, events_to_delete)
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

    async def gather_events(self, sports: list[Sport], eventIds: list[int] = None):
        if not self.session_token:
            await self.authenticate()

        sport_id_map = {v: k for k, v in self.get_sportids().items()}
        url = f"{self.BASE_URL}/listEvents/"

        filter = {
            # "marketTypeCodes": self.markets,
            "inPlayOnly": True
        }
        
        if eventIds:
            filter["eventIds"] = eventIds
            return await self.get(url, self.get_headers(), {"filter": filter})

        result = {}
        for sport in sports:
            filter["eventTypeIds"] = [sport_id_map[sport.pk]]
            response = await self.get(url, self.get_headers(), {"filter": filter})
            result[sport.pk] = response

        return result

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
        result = []
        for sport_id, sport_data in data.items():
            events = sport_data.get('result', [])
            for event in events:
                details = event.get('event', {})
                names = details['name'].split(' v ')
                if len(names) == 2:
                    home, away = names
                    result.append(EventModel(
                        event_id=details['id'],
                        league_id= 0,
                        time=self.parse_event_time(details.get('openDate')),
                        home=home,
                        away=away,
                        selected=False,
                        sportsbook_id=self.sportsbook.pk,
                        sport_id=sport_id
                    ))
        return result

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
    
    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        events_to_update, events_to_delete = [], []
        for event in events:
            try:
                matches = event_response[0]['result']
                match = next((match for match in matches if int(match.get('event', {}).get('id', 0)) == event.event_id), None)
                if not match:
                    events_to_delete.append(event)
                    continue
                event.time = self.parse_event_time(match.get('event', {}).get('openDate')),
                events_to_update.append(event)
            except Exception as ex:
                print(f"Exception in map_events_selected Betfair: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete
    
    def map_odds_selected(self, events: list[Event], odds_response: list[object]) -> list[Odd]:
        event_dict = { event.event_id: event for event in events }
        odds_to_update = []
        for data in odds_response:
            try:
                event_id = int(data[0][1]['matchId'])
                event = event_dict.get(event_id)
                if event:
                    self.update_event_odds(event, data[0][1]['bets'], odds_to_update)
            except Exception as ex:
                print(f"Exception in map_odds_selected Betfair: {str(ex)}.")
                continue                   
        
        return odds_to_update