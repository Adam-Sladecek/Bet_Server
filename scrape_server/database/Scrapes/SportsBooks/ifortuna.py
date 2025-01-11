import aiohttp
from database.Scrapes.SportsBooks.scraper import Scraper
from database.Scrapes.dataclass_models import PriceModel
from database.models import Price, Sport, Event

class IfortunaScraper(Scraper):
    def get_driver(self): return None
    def close_driver(self): pass
    
    def get_sportids(self) -> dict[str, int]: 
        return {
            'LSKFOOTBALL': 1, #socker
            'LSKHOCKEY': 2, #hokej
            'LSKTENNIS': 3, #tenis
            'LSKBASKETBALL': 4, #basketbal
            'LSKHANDBALL': 5, #handball
            'LSKVOLLEYBALL': 6, #volejbal
            'LSKTABLE_TENNIS': 7, #stolny tenis
            6: 8, # box
        }
        
    async def gather_events(self, sports: list[Sport]) -> dict[int, dict]:
        url = 'https://api.ifortuna.sk/live3/api/live/matches/overview'
        async with aiohttp.ClientSession() as session:
            response = await self.get(session, url, {}, {})
            if not response:
                return {}
            
            sport_ids = self.get_sportids()
            allowed_sport_ids = { sport.pk for sport in sports }
            response = {
                sport_id: obj
                for obj in response
                if (sport_id := sport_ids.get(obj['id'])) in allowed_sport_ids
            }

            return response

    async def gather_prices(self, events: list[Event]) -> dict[int, object]:
        data = {
            event.pk: f'https://api.ifortuna.sk/live3/api/live/matches/detail/LSK{event.event_id}'
            for event in events
        }
        results = await self.gather_data(data, {}, {})

        return results
    
    def map_events(self, data: dict[int, dict]) -> list[Event]:
        events = []
        for sport_id, result in data.items():
            try:
                for league in result.get('leagues', []): 
                    for match in league.get('matches', []):
                        events.append(self.create_event(sport_id, match))
            except Exception as ex: 
                print(f"Exception in map_events Ifortuna: {str(ex)}.")
                continue  

        return events
    
    def create_event(self, sport_id: int, match: dict) -> Event:
        event_id = int(match['id'].replace('LSK', ''))
        return Event(
            event_id=event_id,
            time=match['overview']['gameTime']['sk_SK'],
            home=match['team1Names']['sk_SK'],
            away=match['team2Names']['sk_SK'],
            is_default=self.sportsbook.is_default,
            sportsbook=self.sportsbook,
            sport_id=sport_id,
        )
    
    def map_prices(self, events: list[Event], data: dict[int, object]) -> tuple[list[PriceModel], list[Price]]:
        prices_to_create, prices_to_update = [], []
        allowed_markets = self.price_helper.get_allowed_markets()
        
        for event in events:
            dataset = data.get(event.pk)
            if not dataset: 
                for price in event.prices.all():
                    price.locked = True
                    prices_to_update.append(price)
                continue
            
            home, away = self.get_teams(dataset)

            # populate bet_dict with fetched prices
            bet_dict = {} 

            for group in dataset.get('groups', []) or []:
                for market in group.get('markets', []):
                    market_id = market['marketTypeId']
                    if market_id not in allowed_markets:
                        continue

                    subname = market['subNames']['sk_SK']
                    for priceArray in market.get('odds', {}).values():
                        for price in priceArray:
                            _, price_id, _ = self.extract_price_details(price)
                            bet_dict[price_id] = price

            # Update existing prices
            for price in event.prices.all():
                price_data = bet_dict.pop(price.price_id, None)
                self.update_price(price, price_data)
                prices_to_update.append(price)
            
            # Create new prices
            for price_id, price_data in bet_dict.items():
                price = self.create_new_price(event, price_id, price_data)
                if price:
                    prices_to_create.append(price)
        
        return prices_to_create, prices_to_update   

    def extract_price_details(self, price: object):
        return (
            price["value"],
            int(price['id'].replace('LSK', '')),
            price["displayType"] != 'OPEN' or price["value"] < 1
        )
        
    def update_price(self, price: Price, price_data: object):
        odds, _, locked = self.extract_price_details(price_data)
        price.movement = self.get_movement(price.odd, odds)
        price.odds = odds
        price.locked = locked
        
    def process_prices(self, dataset: object, event_id: int, allowed_market_ids: set[str]):
        for group in dataset.get('groups', []) or []:
            for market in group.get('markets', []):
                market_id = market['marketTypeId']
                if market_id not in allowed_market_ids:
                    continue
                odds_to_create, odds_to_update = self.map_market_odds(
                    market, event_id, home, away, odds_to_create, odds_to_update
                )
        return odds_to_create, odds_to_update

    def get_teams(self, dataset: object):
        try:
            return (
                dataset["participants"]['HOME']['name']['sk_SK'],
                dataset["participants"]['AWAY']['name']['sk_SK']
            )
        except Exception:
            return None, None

    def map_market_odds(self, market, event_id: int, home: str, away: str, existing_match_odds: dict, odds_to_create: list, odds_to_update: list):
        subname = market['subNames']['sk_SK']
        for oddArray in market.get('odds', {}).values():
            for odd in oddArray:
                try:
                    odds, odd_id, locked = self.extract_odd_details(odd)
                    description = self.create_odd_description(subname, odd, home, away)
                    if odd_id in existing_match_odds:
                        self.update_existing_odd(existing_match_odds, odd_id, odds, locked, odds_to_update)
                        continue
                    odds_to_create.append(self.create_odd_model(odd_id, event_id, market['marketTypeId'], odds, description, locked))
                except Exception as ex:
                    print(f"Exception in map_market_odds Ifortuna: {str(ex)}.")
        return odds_to_create, odds_to_update



    def create_odd_model(self, odd_id: int, event_id: int, market_id: str, odds, description: str, locked: bool):
        return PriceModel(
            id=None,
            odd_id=odd_id,
            code=0,
            movement=1,
            odd=odds,
            is_default=self.sportsbook.is_default,
            selected=False,
            locked=locked,
            event_id=event_id,
            sportsbook_id=self.sportsbook.pk,
            description=description,
            market_id=market_id,
        )
    
    def create_odd_description(self, subname: str, odd, home: str, away: str):
        longName = odd['longNames']['sk_SK']
        description = f'{subname} {longName}'.replace(home, "*1*").replace(away, "*2*")
        description = description.replace("  ", " ").replace("  ", " ").strip()
        return description