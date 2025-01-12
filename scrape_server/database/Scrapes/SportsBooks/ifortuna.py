import aiohttp
from database.Scrapes.SportsBooks.scraper import Scraper
from database.Scrapes.dataclass_models import PriceModel
from database.models import Price, Sport, Event
from database.enums import Movement

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
            

            # populate bet_dict with fetched prices
            bet_dict = {} 

            for group in dataset.get('groups', []) or []:
                for market in group.get('markets', []):
                    market_id = market['marketTypeId']
                    if market_id not in allowed_markets:
                        continue

                    subname = market['subNames']['sk_SK']
                    for priceArray in market.get('odds', {}).values():
                        for price_data in priceArray:
                            price_id = int(price_data['id'].replace('LSK', ''))
                            bet_dict[price_id] = (subname, price_data)

            # Update existing prices
            for price in event.prices.all():
                _, price_data = bet_dict.pop(price.price_id, (None, None))
                self.update_price(price, price_data)
                prices_to_update.append(price)

            # Create new prices
            home, away = self.get_teams(dataset)
            for price_id, (subname, price_data) in bet_dict.items():
                price = self.create_new_price(event, price_id, price_data, subname, home, away)
                if price:
                    prices_to_create.append(price)
        
        return prices_to_create, prices_to_update   

    def extract_price_details(self, price_data: object) -> tuple[float, bool]:
        return (
            price_data["value"],
            price_data["displayType"] != 'OPEN' or price_data["value"] < 1
        )
        
    def update_price(self, price: Price, price_data: object) -> None:
        if not price_data:
            price.locked = True
            return
        
        odds, locked = self.extract_price_details(price_data)
        price.movement = self.get_movement(price.odds, odds)
        price.odds = odds
        price.locked = locked
        
    def create_new_price(self, event: Event, price_id: int, price_data: object, subname: str, home: str, away: str) -> PriceModel | None:
        try:
            description = self.create_price_description(subname, price_data, home, away)
            odds, locked = self.extract_price_details(price_data)

            price = Price(
                price_id = price_id,
                movement = Movement.UP.value,
                odds = odds,
                is_default = self.sportsbook.is_default,
                selected = True,
                locked = locked,
                event = event,
                sportsbook = self.sportsbook,
            )

            return PriceModel(None, description, price)
        except Exception as ex:
            print(f"Exception in create_new_price Ifortuna: {str(ex)}.")
            return None

    def get_teams(self, dataset: object) -> tuple[str, str]:
        try:
            return (
                dataset["participants"]['HOME']['name']['sk_SK'],
                dataset["participants"]['AWAY']['name']['sk_SK']
            )
        except Exception:
            return None, None
    
    def create_price_description(self, subname: str, price_data: object, home: str, away: str) -> str:
        longName = price_data['longNames']['sk_SK']
        description = f'{subname} {longName}'
        description = self.replace_by_tokens(description, [
            (home, " *1* "),
            (away, " *2* "),
        ])

        return description.replace("  ", " ").replace("  ", " ").strip()
