from .scraper import Scraper
from ..dataclass_models import EventModel, OddModel
from ...models import Odd, Sport, Event, SportsbookMarket

class NikeScraper(Scraper):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_driver()    

    def get_driver(self):
        return None
    
    def close_driver(self):
        pass
    
    async def gather_events(self, sports: list[Sport]):
        data = {
            sport.pk: f'https://push.nike.sk/snapshot?format=v2&path=/n1/overview/{getattr(self.sportsbook, sport.url)}/tournaments/' 
            for sport in sports
        }
        
        return await self.gather_data(data, {})

    async def gather_odds(self, events):
        data = {
            event.event_id: f'https://push.nike.sk/snapshot?format=v2&path=/n1/match/{event.event_id}/bets/portal/'
            for event in events
        }
        results = await self.gather_data(data, {})
        return list(results.values())
    
    def map_events(self, data: dict[int, object]) -> list[EventModel]:
        events = []
        for sport_id, result in data.items():
            try:
                matches = result[0][1]['matches']
                events.extend(self.map_single_event(sport_id, match) for match in matches)
            except Exception as ex: 
                print(f"Exception in map_events Nike: {str(ex)}.")
                continue  

        return events
    
    def map_single_event(self, sport_id: int, match: dict) -> EventModel:
        event_id = int(match['id'])
        time = self.get_time_from_match(match)
        home = match['home']['sk']
        away = match['away']['sk']
        return EventModel(
            id=None,
            event_id=event_id,
            league_id=0,
            time=time,
            home=home,
            away=away,
            is_default=self.sportsbook.is_default,
            selected=False,
            sportsbook_id=self.sportsbook.pk,
            sport_id=sport_id,
            available_sportsbooks=[],
            odd_count=0,
        )
    
    def map_odds(self, data: list[object]) -> tuple[list[OddModel], list[Odd]]:
        if not any(data):
            raise Exception('No details retrieved.')
        
        odds_to_create, odds_to_update = [], []
        allowed_market_ids = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = self.odd_helper.get_existing_odds(True)
        for dataset in data:
            if dataset:
                self.map_dataset(dataset, allowed_market_ids, existing_odds, odds_to_create, odds_to_update) 
        return odds_to_create, odds_to_update       

    def map_dataset(self, dataset: object, allowed_market_ids: set[str], existing_odds: dict[int, dict[tuple, object]], odds_to_create: list, odds_to_update: list):
        for bet in dataset[0][1]['bets']:
            try:
                if bet['marketId'] not in allowed_market_ids:
                    continue
                
                odd_id = int(bet['id'])
                event_id = int(bet['matchId'])
                home = bet["participants"][0]['sk']
                away = bet["participants"][1]['sk'] if len(bet["participants"]) == 2 else None
                existing_match_odds = existing_odds[event_id]

                for odd in bet['selections']:
                    code = odd["code"]
                    locked = odd["locked"] or not odd["enabled"]

                    if (odd_id, code) in existing_match_odds:
                        existing_odd = existing_match_odds.pop((odd_id, code))
                        existing_odd.movement = self.get_movement(existing_odd.odd, odd["odds"])
                        existing_odd.odd = odd["odds"]
                        existing_odd.locked = locked
                        odds_to_update.append(existing_odd)
                        continue

                    description = self.generate_description(bet, odd, home, away)
                    odds_to_create.append(OddModel(
                        id=None,
                        odd_id=odd_id,
                        code=code,
                        movement=1,
                        odd=odd["odds"],
                        is_default=self.sportsbook.is_default,
                        selected=False,
                        locked=locked,
                        event_id=event_id,
                        sportsbook_id=self.sportsbook.pk,
                        description=description,
                        market_id=bet['marketId']
                    ))
            except Exception as ex:
                    print(f"Exception in map_odds Nike: {str(ex)}.")
                    continue  
        
    def generate_description(self, bet, odd, home: str, away: str) -> str:
        description = f"{bet['header']['sk']} {odd['name']['sk']}"
        description = description.replace(home, "*1*")
        if away is not None:
            description = description.replace(away, "*2*")
        return description.replace("  ", " ").replace("  ", " ").strip()
                    
    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        events_to_update, events_to_delete = [], []
        for event in events:
            try:
                match = self.find_match_in_response(event_response, event)
                if not match:
                    events_to_delete.append(event)
                    continue
                event.time = self.get_time_from_match(match)
                events_to_update.append(event)
            except Exception as ex:
                print(f"Exception in map_events_selected Nike: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def find_match_in_response(self, event_response: dict[int, object], event: Event) -> dict | None:
        result = event_response.get(event.sport.pk)
        if result:
            matches = result[0][1]['matches']
            return next((match for match in matches if int(match['id']) == event.event_id), None)
        return None
    
    def get_time_from_match(self, match) -> str:
        time = match['timer'].get('currentPeriod', {}).get('sk', '')
        timestamp, countdown = match['timer'].get('timestamp'), bool(match['timer'].get('countDown', False))
        if timestamp:
            seconds = match['timer'].get('matchSeconds', 0)
            timestamp -= seconds * 1000
            converted_time = self.convert_timestamp_to_time_string(timestamp) if not countdown else self.convert_seconds_to_time_string(seconds)
            time += f' {converted_time}'
        return time

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
                print(f"Exception in map_odds_selected Nike: {str(ex)}.")
                continue                   
        
        return odds_to_update

    def update_event_odds(self, event: Event, bets: list[dict], odds_to_update: list[Odd]):
        bet_dict = {int(bet['id']): bet for bet in bets}
        for odd in event.odds.filter(parent__selected=True):
            data_bet = bet_dict.get(odd.odd_id)
            if not data_bet:
                odd.locked = True
                odds_to_update.append(odd)
                continue
            self.update_single_odd(data_bet, odd, odds_to_update)

    def update_single_odd(self, data_bet: dict, odd: Odd, odds_to_update: list[Odd]):
        for index, data_odd in enumerate(data_bet['selections']):
            if odd.code == data_odd["code"]:
                odd.movement = self.get_movement(odd.odd, data_odd["odds"])
                odd.odd = data_odd["odds"]
                odd.locked = data_odd["locked"] or not data_odd["enabled"]
                odds_to_update.append(odd)
                break
            if index == len(data_bet['selections']) - 1:
                odd.locked = True
                odds_to_update.append(odd)