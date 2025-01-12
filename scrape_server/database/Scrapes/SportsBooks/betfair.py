from datetime import datetime
import aiohttp
from database.enums import Movement
from database.models import Sport, Sportsbook, Event, Price
from database.Scrapes.SportsBooks.scraper import Scraper
from database.Scrapes.dataclass_models import PriceModel

class BetfairScraper(Scraper):
    BASE_URL = "https://api.betfair.com/exchange/betting/rest/v1.0"
    
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]) -> None:
        super().__init__(sportsbook, sports)
        self.session_token = "h0z8dOrm1huD8ORIJk3pHSNf7KT78RG7VbSrKlev8HM="
        self.app_key = "WAVvPmAtlpnmt9Er" # Get from Betfair Developer Program
        
    def get_driver(self): pass
    def close_driver(self): pass

    def get_headers(self) -> dict[str, str]:
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

    def refresh_prices(self) -> None:
        try:
            events = self.event_helper.get_selected_events()
            if len(events) == 0: 
                return

            loop = self.get_loop()
            markets = loop.run_until_complete(self.gather_markets(events))
            prices_response = loop.run_until_complete(self.gather_prices(markets))
            prices_to_create, prices_to_update = self.map_prices(events, prices_response, markets)
            self.price_helper.update_prices(prices_to_create, prices_to_update)

        except Exception as ex:
            print(f"Refresh prices in {self.sportsbook.name} failed. Exception: {str(ex)}.")

    async def gather_markets(self, events: list[Event]) -> list[object]:
        event_ids = [str(event.event_id) for event in events]
        url = f"{self.BASE_URL}/listMarketCatalogue/"

        async with aiohttp.ClientSession() as session:
            data = {"filter": {"eventIds": event_ids}, "maxResults": 1000, "marketProjection": ["EVENT", "RUNNER_DESCRIPTION"]}
            results = await self.post(session, url, self.get_headers(), data) 

        return [result for result in results if result['marketName'] in self.allowed_markets]

    async def gather_events(self, sports: list[Sport]) -> dict[int, list[object]]:
        sport_id_map = {v: k for k, v in self.get_sportids().items()}
        base_url = f"{self.BASE_URL}/listEvents/"
        
        url_dict = {}
        data_dict = {}
        
        for sport in sports:
            url_dict[sport.pk] = base_url
            data_dict[sport.pk] = {
                'filter': {
                    'inPlayOnly': True,
                    'eventTypeIds': [sport_id_map[sport.pk]]
                }
            }
        
        result = await self.gather_data(url_dict, self.get_headers(), data_dict, is_post=True)
        
        return {sport_id: (data if data else []) for sport_id, data in result.items()}

    async def gather_prices(self, markets: list[object]) -> list[object]:
        market_ids = [market['marketId'] for market in markets]
        data = {
            "marketIds": market_ids,
            "priceProjection": {
                "priceData": ["EX_BEST_OFFERS"],
                "virtualise": True
            }
        }
        
        url = f"{self.BASE_URL}/listMarketBook/"
        
        async with aiohttp.ClientSession() as session:
            response = await self.post(session, url, self.get_headers(), data)
        
        return response

    def map_events(self, data) -> list[Event]:
        events = []
        for sport_id, sport_data in data.items():
            events = sport_data
            for event in events:
                details = event.get('event', {})
                names = details.get('name', '').split(' v ')
                if len(names) == 2:
                    home, away = names
                    events.append(Event(
                        event_id = int(details['id']),
                        time = self.parse_event_time(details.get('openDate')),
                        home = home,
                        away = away,
                        is_default = self.sportsbook.is_default,
                        sportsbook = self.sportsbook,
                        sport_id = sport_id,
                    ))
        
        return events

    def map_prices(self, events: list[Event], prices_response: list[object], markets: list[object]) -> tuple[list[PriceModel], list[Price]]:
        prices_to_create = []
        prices_to_update = []
        
        for event in events:
            market_id = next((market['marketId'] for market in markets if market['event']['id'] == event.event_id), None)
            if market_id is None:
                for price in event.prices.all():
                    price.locked = True
                    prices_to_update.append(price)
                continue

        for marketBook in data:
            market_id = marketBook['marketId']
            market = next((market for market in markets if market['marketId'] == market_id), {})
            event_id = int(market.get('event').get('id'))

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
                    odds_to_create.append(PriceModel(
                        id=None,
                        odd_id=odd_id,
                        movement=Movement.UP,
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

        return prices_to_create, prices_to_update

    def parse_event_time(self, time_str: str) -> str:
        if not time_str:
            return "0:00'"
        try:
            event_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            time_diff = datetime.now() - event_time
            total_seconds = int(time_diff.total_seconds())

            return self.convert_seconds_to_time_string(total_seconds)
        except:
            return "0:00'" 