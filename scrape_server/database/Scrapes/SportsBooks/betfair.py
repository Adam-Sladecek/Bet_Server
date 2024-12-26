import asyncio
import json
from datetime import datetime
from typing import Optional
import aiohttp
from ...models import Sport, Sportsbook, Event, Odd, SportsbookMarket
from ..helpers import OddHelper, EventHelper
from ..dataclass_models import EventModel, OddModel
from .scraper import Scraper

class BetfairScraper(Scraper):
    BASE_URL = "https://api.betfair.com/exchange/betting/rest/v1.0"
    
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        super().__init__(sportsbook, sports)
        self.session_token = "0KbKRHrJeWEi+p7lsItHctVQsh60f5DvwEHlIIH4s3M="
        self.app_key = "WAVvPmAtlpnmt9Er" # Get from Betfair Developer Program
        self.markets = [sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()]
        
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_driver()
        
    def get_driver(self):
        # Not needed for REST API
        pass

    def close_driver(self):
        # Not needed for REST API
        pass

    def get_headers(self):
        return {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'content-type': 'application/json'
        }

    def get_sportids(self) -> dict[str, int]: 
        return {
            '1': 1, #soccer
            '7524': 2, #hockey
            '2': 3, #tennis
            '7522': 4, #basketball
            '468328': 5, #handball
            '998917': 6, #volleyball
            '': 7, #table tennis
            '6': 8, #boxing
        }

    def get_data(self):
        try:
            events, sport_ids = self.event_helper.get_selected_events()
            if len(events) == 0: 
                return
            sports = [sport for sport in self.sports if sport.pk in sport_ids]
            loop = self.get_loop()
            event_ids = [event.event_id for event in events]
            event_response = loop.run_until_complete(self.gather_events(sports, event_ids))
            mapped_events, events_to_delete = self.map_events_selected(events, event_response)
            self.event_helper.update_selected_events(mapped_events, events_to_delete)
            events = [event for event in events if event.pk is not None]
            event_ids = [event.event_id for event in events]
            allowed_market_ids = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
            markets = loop.run_until_complete(self.gather_markets(event_ids, allowed_market_ids))
            market_ids = [market['marketId'] for market in markets]
            odds_response = loop.run_until_complete(self.gather_odds(events, market_ids))
            odds_to_create, odds_to_update = self.map_odds(odds_response, markets)
            self.odd_helper.update_odds(odds_to_create, odds_to_update)

        except Exception as ex:
            print(f"Get data in {self.sportsbook.name} failed. Exception: {str(ex)}.")

    def import_all_data(self):
        try:
            loop = self.get_loop()
            event_response = loop.run_until_complete(self.gather_events(self.sports))
            events = self.map_events(event_response)
            self.event_helper.update_events(events)    

        except Exception as ex:
            print(f"Import in {self.sportsbook.name} failed. Exception: {str(ex)}.")  

    async def gather_markets(self, event_ids: list[int], allowed_market_ids: list[str]):
        event_ids = [str(event_id) for event_id in event_ids]
        url = f"{self.BASE_URL}/listMarketCatalogue/"
        response = await self.post(url, self.get_headers(), {"filter": {"eventIds": event_ids}, "maxResults": 1000, "marketProjection": ["EVENT", "RUNNER_DESCRIPTION"]})
        results = response
        return [result for result in results if result['marketName'] in allowed_market_ids]

    async def gather_events(self, sports: list[Sport], eventIds: list[int] = None):
        sport_id_map = {v: k for k, v in self.get_sportids().items()}
        url = f"{self.BASE_URL}/listEvents/"

        filter = {
            'inPlayOnly': True
        }
        
        if eventIds:
            filter['eventIds'] = eventIds
            response = await self.post(url, self.get_headers(), {'filter': filter})
            return response
        
        result = {}
        # Create all tasks first
        tasks = []
        for sport in sports:
            sport_filter = filter.copy()
            sport_filter['eventTypeIds'] = [sport_id_map[sport.pk]]
            tasks.append(self.post(url, self.get_headers(), {'filter': sport_filter}))
        
        # Wait for all tasks to complete
        responses = await asyncio.gather(*tasks)
        
        # Process responses
        for sport, response in zip(sports, responses):
            if response:
                result[sport.pk] = response
            else:
                result[sport.pk] = []

        return result

    async def gather_odds(self, events: list[EventModel], market_ids: list[str]):
        params = {
            "marketIds": market_ids,
            "priceProjection": {
                "priceData": ["EX_BEST_OFFERS"],
                "virtualise": True
            }
        }
        
        url = f"{self.BASE_URL}/listMarketBook/"
        response = await self.post(url, self.get_headers(), params)
        return response

    def map_events(self, data) -> list[EventModel]:
        result = []
        for sport_id, sport_data in data.items():
            events = sport_data
            for event in events:
                details = event.get('event', {})
                names = details['name'].split(' v ')
                if len(names) == 2:
                    home, away = names
                    result.append(EventModel(
                        id=None,
                        league_id=0,
                        event_id=int(details['id']),
                        time=self.parse_event_time(details.get('openDate')),
                        home=home,
                        away=away,
                        selected=False,
                        odd_count=0,
                        sport_id=sport_id,
                        sportsbook_id=self.sportsbook.pk,
                        is_default=self.sportsbook.is_default,
                        available_sportsbooks=[],
                    ))
        return result

    def map_odds(self, data, markets) -> tuple[list[OddModel], list[Odd]]:
        odds_to_create = []
        odds_to_update = []
        existing_odds = self.odd_helper.get_existing_odds()
        for marketBook in data:
            market_id = marketBook['marketId']
            market = next((market for market in markets if market['marketId'] == market_id), {})
            event_id = int(market.get('event').get('id'))
            match_odds = existing_odds.get(event_id, {})

            for runner in market.get('runners', []):
                opp_name = f"{market.get('marketName', '')} {runner.get('runnerName', '')}"
                home, away = market.get('event', {}).get('name', '').split(' v ')
                opp_name = opp_name.replace(home, "*1*").replace(away, "*2*")
                selection_id = runner.get('selectionId')
                marketbook_runner = next((runner for runner in marketBook.get('runners', []) if runner.get('selectionId') == selection_id), {})
                bets = marketbook_runner.get('ex', {}).get('availableToLay', [])
                best_price = next((bet.get('price') for bet in sorted(bets, key=lambda x: x.get('size')) if bet.get('size') > 100), 0)
                odd_id = runner['selectionId']
                locked = marketbook_runner.get('status', '') != 'ACTIVE' or best_price == 0
                
                if odd_id in match_odds:
                    existing_odd = match_odds[odd_id]
                    existing_odd.movement = self.get_movement(existing_odd.odd, best_price)
                    existing_odd.locked = locked
                    existing_odd.odd = best_price
                    odds_to_update.append(existing_odd)
                else:
                    odds_to_create.append(OddModel(
                        id=None,
                        odd_id=odd_id,
                        movement=1,
                        is_default=self.sportsbook.is_default,
                        selected=True,
                        locked=locked,
                        sportsbook_id=self.sportsbook.pk,
                        event_id=event_id,
                        code=0,
                        description=opp_name,
                        odd=best_price,
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
    
    def map_events_selected(self, events: list[Event], event_response: list[object]) -> tuple[list[Event], list[Event]]:
        events_to_update, events_to_delete = [], []
        for event in events:
            try:
                matches = event_response
                if not matches:
                    events_to_delete.append(event)
                    continue
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
    
    def map_odds_selected(self, data, markets) -> tuple[list[OddModel], list[Odd]]:
        pass
