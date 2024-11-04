from .scraper import Scraper
from ..dataclass_models import EventModel, OddModel
from ...models import Odd, Sport, Event, SportsbookMarket

class IfortunaScraper(Scraper):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_driver()

    def get_driver(self):
        return None
    
    def close_driver(self):
        pass
    
    async def gather_events(self, sports: list[Sport]):
        data = { 1: 'https://api.ifortuna.sk/live3/api/live/matches/overview' }
        dict_response  = await self.gather_data(data, {})
        result = dict_response.get(1, [])
        sport_ids = self.get_sportids()
        allowed_sport_ids = { sport.pk for sport in sports }
        response = {
            sport_id: obj
            for obj in result
            if (sport_id := sport_ids.get(obj['id'])) in allowed_sport_ids
        }
        return response

    async def gather_odds(self, events):
        data = {
            event.event_id: f'https://api.ifortuna.sk/live3/api/live/matches/detail/LSK{event.event_id}'
            for event in events
        }
        results = await self.gather_data(data, {})
        return results
    
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
    
    def map_events(self, data: dict[int, object]) -> list[EventModel]:
        events = []
        for sport_id, result in data.items():
            try:
                for league in result.get('leagues', []): 
                    for match in league.get('matches', []):
                        events.append(self.create_event_model(sport_id, match))
            except Exception as ex: 
                print(f"Exception in map_events Ifortuna: {str(ex)}.")
                continue  

        return events
    
    def create_event_model(self, sport_id, match) -> EventModel:
        event_id = int(match['id'].replace('LSK', ''))
        return EventModel(
            id=None,
            event_id=event_id,
            league_id=0,
            time=match['overview']['gameTime']['sk_SK'],
            home=match['team1Names']['sk_SK'],
            away=match['team2Names']['sk_SK'],
            is_default=self.sportsbook.is_default,
            selected=False,
            sportsbook_id=self.sportsbook.pk,
            sport_id=sport_id,
            available_sportsbooks=[],
            odd_count=0,
        )
    
    def map_odds(self, data: dict[int, object]) -> tuple[list[OddModel], list[Odd]]:
        if all(element is None for element in data.values()):
            raise Exception('No details retrieved.')
        
        odds_to_create, odds_to_update = [], []
        allowed_market_ids = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = self.odd_helper.get_existing_odds(self.sportsbook)
        for event_id, dataset in data.items():
            if dataset is None: 
                continue
            odds_to_create, odds_to_update = self.process_odds(dataset, event_id, allowed_market_ids, existing_odds, odds_to_create, odds_to_update)
        return odds_to_create, odds_to_update   

    def process_odds(self, dataset: object, event_id: int, allowed_market_ids: set[str], existing_odds: dict[int, dict], odds_to_create: list, odds_to_update: list):
        home, away = self.get_teams(dataset)
        existing_match_odds = existing_odds.get(event_id, {})

        for group in dataset.get('groups', []):
            for market in group.get('markets', []):
                market_id = market['marketTypeId']
                if market_id not in allowed_market_ids:
                    continue
                odds_to_create, odds_to_update = self.map_market_odds(
                    market, event_id, home, away, existing_match_odds, odds_to_create, odds_to_update
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

    def extract_odd_details(self, odd):
        return (
            odd["value"],
            int(odd['id'].replace('LSK', '')),
            odd["displayType"] != 'OPEN' or odd["value"] < 1
        )

    def update_existing_odd(self, existing_match_odds: list, odd_id: int, odds, locked: bool, odds_to_update: list):
        existing_odd = existing_match_odds.pop(odd_id)
        existing_odd.movement = self.get_movement(existing_odd.odd, odds)
        existing_odd.odd = odds
        existing_odd.locked = locked
        odds_to_update.append(existing_odd)

    def create_odd_model(self, odd_id: int, event_id: int, market_id: str, odds, description: str, locked: bool):
        return OddModel(
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
    
    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        events_to_update, events_to_delete = [], []
        for event in events:
            try:
                if not self.process_event_update(event, event_response, events_to_update):
                    events_to_delete.append(event)
            except Exception as ex:
                print(f"Exception in map_events_selected Ifortuna: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def process_event_update(self, event: Event, event_response: dict[int, object], events_to_update: list):
        result = event_response.get(event.sport.pk)
        if result is None:
            return False
        for league in result.get('leagues', []):
            if match := self.find_match_in_league(league, event.event_id):
                event.time = match['overview']['gameTime']['sk_SK']
                events_to_update.append(event)
                return True
        return False

    def find_match_in_league(self, league, event_id: int):
        for match in league.get('matches', []):
            if int(match['id'].replace('LSK', '')) == event_id:
                return match
        return None
    
    def map_odds_selected(self, events: list[Event], odds_response: dict[int, object]) -> list[Odd]:
        event_dict = {event.event_id: event for event in events}
        odds_to_update = []
        for event_id, dataset in odds_response.items():
            try:
                event = event_dict.get(event_id)
                bet_dict = {}
                if not event or dataset is None or dataset.get('groups') is None:
                    continue
                bet_dict = self.extract_odds_from_dataset(dataset)
                odds_to_update.extend(self.update_event_odds(event, bet_dict))
            except Exception as ex:
                print(f"Exception in map_odds_selected Ifortuna: {str(ex)}.")
                continue                   
        
        return odds_to_update
    
    def extract_odds_from_dataset(self, dataset: dict) -> dict[int, dict]:
        return {
            int(odd['id'].replace('LSK', '')): odd
            for group in dataset.get('groups', []) for market in group.get('markets', [])
            for oddArray in market.get('odds', {}).values() for odd in oddArray
        }
    
    def update_event_odds(self, event: Event, bet_dict: dict[int, dict]) -> list[Odd]:
        odds_to_update = []
        for odd in event.odds.filter(parent__selected=True).all():
            data_odd = bet_dict.get(odd.odd_id)

            if data_odd is None:
                odd.locked = True
            else:
                odds_value = data_odd["value"]
                odd.locked = data_odd["displayType"] != 'OPEN' or odds_value < 1
                odd.movement = self.get_movement(odd.odd, odds_value)
                odd.odd = odds_value

            odds_to_update.append(odd)

        return odds_to_update