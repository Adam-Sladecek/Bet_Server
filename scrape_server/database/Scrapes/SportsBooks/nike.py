from datetime import datetime
from database.enums import Movement
from database.Scrapes.SportsBooks.scraper import Scraper
from database.Scrapes.dataclass_models import PriceModel
from database.models import Price, Sport, Event

class NikeScraper(Scraper):
    def get_driver(self): pass
    def close_driver(self): pass
    
    def get_url_segment_dict(self) -> dict[int, str]:
        return { 1: 'futbal', 2: 'hokej', 3: 'tenis', 4: 'basketbal', 5: 'hadzana', 6: 'volejbal', 7: 'stolny-tenis', 8: 'box' }
    
    async def gather_events(self, sports: list[Sport]) -> dict[int, object]:
        url_segment_dict = self.get_url_segment_dict()
        url_dict = {
            sport.pk: f'https://push.nike.sk/snapshot?format=v2&path=/n1/overview/{url_segment_dict[sport.pk]}/tournaments/' 
            for sport in sports
        }
        
        return await self.gather_data(url_dict, {}, {})

    async def gather_prices(self, events: list[Event]) -> dict[int, object]:
        url_dict = {
            event.pk: f'https://push.nike.sk/snapshot?format=v2&path=/n1/match/{event.event_id}/bets/portal/'
            for event in events
        }

        return await self.gather_data(url_dict, {}, {})
    
    def map_events(self, data: dict[int, object]) -> list[Event]:
        events = []
        for sport_id, result in data.items():
            try:
                matches = result[0][1]['matches']
                events.extend([self.map_single_event(sport_id, match) for match in matches])
            except Exception as ex: 
                print(f"Exception in map_events Nike: {str(ex)}.")
                continue  

        return events
    
    def map_single_event(self, sport_id: int, match: dict) -> Event:
        event_id = int(match['id'])
        time = self.get_time_from_match(match)
        home = match['home']['sk']
        away = match['away']['sk']

        return Event(
            event_id=event_id,
            time=time,
            home=home,
            away=away,
            is_default=self.sportsbook.is_default,
            sportsbook=self.sportsbook,
            sport_id=sport_id,
        )
        
    def get_time_from_match(self, match) -> str:
        time = match['timer'].get('currentPeriod', {}).get('sk', '')
        timestamp, countdown = match['timer'].get('timestamp'), bool(match['timer'].get('countDown', False))
        if timestamp:
            seconds = match['timer'].get('matchSeconds', 0)
            timestamp -= seconds * 1000
            converted_time = self.convert_timestamp_to_time_string(timestamp) if not countdown else self.convert_seconds_to_time_string(seconds)
            time += f' {converted_time}'

        return time
                    
    def convert_timestamp_to_time_string(self, timestamp_ms: int) -> str:
        timestamp_time = datetime.fromtimestamp(timestamp_ms / 1000)
        time_difference = datetime.now() - timestamp_time
        total_seconds = int(time_difference.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        return f"{minutes}:{seconds:02}'"
    
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
            
            bet_dict = {}
            for bet in dataset[0][1]['bets']:
                if bet['marketId'] not in allowed_markets:
                    continue
                for selection in bet['selections']:
                    key = int(bet['id'] + str(selection['code']))
                    bet_dict[key] = (bet, selection)

            # Update existing prices
            for price in event.prices.all():
                _, selection = bet_dict.pop(price.price_id, (None, None))
                self.update_price(price, selection)
                prices_to_update.append(price)
            
            # Create new prices
            for price_id, (bet, selection) in bet_dict.items():
                price = self.create_new_price(event, price_id, bet, selection)
                if price:
                    prices_to_create.append(price)

        return prices_to_create, prices_to_update       

    def update_price(self, price: Price, selection: dict) -> None:
        if not selection:
            price.locked = True
            return
        
        price.movement = self.get_movement(price.odds, selection["odds"])
        price.odds = selection["odds"]
        price.locked = selection["locked"] or not selection["enabled"]

    def create_new_price(self, event: Event, price_id: int, bet: dict, selection: dict) -> PriceModel | None:
        try:
            if len(bet["participants"]) != 2:
                return None
            
            home = bet["participants"][0]['sk']
            away = bet["participants"][1]['sk']
            locked = selection["locked"] or not selection["enabled"]
            description = self.generate_description(bet, selection, home, away)

            price = Price(
                price_id = price_id,
                movement = Movement.UP.value,
                odds = selection["odds"],
                is_default = self.sportsbook.is_default,
                selected = True,
                locked = locked,
                event = event,
                sportsbook = self.sportsbook,
            )

            return PriceModel(None, description, price)
        except Exception as ex:
            print(f"Exception in create_new_price Nike: {str(ex)}.")
            return None
        
    def generate_description(self, bet: dict, selection: dict, home: str, away: str) -> str:
        description = f"{bet['header']['sk']} {selection['name']['sk']}"
        description = self.replace_by_tokens(description, [
            (home, " *1* "),
            (away, " *2* "),
        ])
        
        return description.replace("  ", " ").replace("  ", " ").strip()
