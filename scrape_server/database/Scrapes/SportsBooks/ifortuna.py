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
        data = {1: 'https://api.ifortuna.sk/live3/api/live/matches/overview'}
        dict = await self.gather_data(data, {})
        result = dict[1]
        sport_ids = self.get_sportids()
        allowed_sport_ids = [sport.pk for sport in sports]
        response = {}
        for obj in result:
            sport_id = sport_ids.get(obj['id'], None)
            if not sport_id or sport_id not in allowed_sport_ids: continue
            response[sport_id] = obj
        return response

    async def gather_odds(self, events):
        data = {}
        for event in events:
            data[event.event_id] = f'https://api.ifortuna.sk/live3/api/live/matches/detail/LSK{str(event.event_id)}'
        results = await self.gather_data(data, {})
        
        return results
    
    def get_sportids(self) -> dict[str, int]: 
        sport_ids = {
            'LSKFOOTBALL': 1, #socker
            'LSKHOCKEY': 2, #hokej
            'LSKTENNIS': 3, #tenis
            'LSKBASKETBALL': 4, #basketbal
            'LSKHANDBALL': 5, #handball
            'LSKVOLLEYBALL': 6, #volejbal
            'LSKTABLE_TENNIS': 7, #stolny tenis
            6: 8, # box
        }
        return sport_ids
    
    def map_events(self, data: dict[int, object]) -> list[EventModel]:
        events: list[EventModel] = []
        for sport_id, result in data.items():
            try:
                leagues = result['leagues']
                for league in leagues: 
                    matches = league['matches']
                    for match in matches:
                        event_id = int(match['id'].replace('LSK', ''))
                        time = match['overview']['gameTime']['sk_SK']
                        home = match['team1Names']['sk_SK']
                        away = match['team2Names']['sk_SK']
                        events.append(EventModel(
                            id=None, 
                            event_id=event_id, 
                            league_id=0,
                            time =time, 
                            home=home, 
                            away=away, 
                            is_default=self.sportsbook.is_default, 
                            selected=False, 
                            sportsbook_id=self.sportsbook.pk, 
                            sport_id=sport_id, 
                            available_sportsbooks=[],
                            odd_count=0,
                        ))
            except Exception as ex: 
                print(f"Exception in map_events Ifortuna: {str(ex)}.")
                continue  

        return events
    
    def map_odds(self, data: dict[int, object]) -> tuple[list[OddModel], list[Odd]]:
        if all(element is None for element in data.values()):
            raise Exception('No details retrieved.')
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        
        allowed_market_ids = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = self.odd_helper.get_existing_odds(self.sportsbook)
        for event_id, dataset in data.items():
            if dataset is None: continue
            try:
                home = dataset["participants"]['HOME']['name']['sk_SK']
                away = dataset["participants"]['AWAY']['name']['sk_SK']
            except Exception as ex: 
                continue
            existing_match_odds = existing_odds[event_id]
            for group in dataset['groups']:
                for market in group['markets']:
                    subname = market['subNames']['sk_SK']
                    market_id = market['marketTypeId']
                    if market_id not in allowed_market_ids: continue
                    for _, oddArray in market['odds'].items():
                        for odd in oddArray:
                            try:
                                odds = odd["value"]
                                odd_id = int(odd['id'].replace('LSK', ''))
                                locked = odd["displayType"] != 'OPEN' or odds < 1
                                if odd_id in existing_match_odds: 
                                    existing_odd = existing_match_odds[odd_id]
                                    del existing_match_odds[odd_id]
                                    existing_odd.movement = self.get_movement(existing_odd.odd, odds)
                                    existing_odd.odd = odds
                                    existing_odd.locked = locked
                                    odds_to_update.append(existing_odd)
                                    continue

                                longName = odd['longNames']['sk_SK']
                                description = f'{subname} {longName}'
                                description = description.replace(home, "*1*").replace(away, "*2*")
                                description = description.replace("  ", " ").replace("  ", " ").strip()
                                odds_to_create.append(OddModel(
                                    id=None,
                                    odd_id = odd_id,
                                    code= 0,
                                    movement= 1,
                                    odd = odds,
                                    is_default=self.sportsbook.is_default,
                                    selected= False,
                                    locked = locked, 
                                    event_id = event_id,
                                    sportsbook_id=self.sportsbook.pk,
                                    description = description,
                                    market_id=market_id
                                ))        
                            except Exception as ex:
                                print(f"Exception in map_odds Ifortuna: {str(ex)}.")
                                continue  

        return odds_to_create, odds_to_update       

    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        events_to_update: list[Event] = []
        events_to_delete: list[Event] = []
        for event in events:
            try:
                result = event_response.get(event.sport.pk, None)
                if result is None: 
                    events_to_delete.append(event)
                    continue
                leagues = result['leagues']
                match = None
                for league in leagues: 
                    matches = league['matches']
                    match = next((match for match in matches if int(match['id'].replace('LSK', '')) == event.event_id), None)
                    if match is not None: break
                if match is None: 
                    events_to_delete.append(event)
                    continue
                time = match['overview']['gameTime']['sk_SK']
                event.time = time    
                events_to_update.append(event)  
            except Exception as ex:
                print(f"Exception in map_events_selected Ifortuna: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def map_odds_selected(self, events: list[Event], odds_response: dict[int, object]) -> list[Odd]:
        event_dict = {event.event_id: event for event in events}
        odds_to_update: list[Odd] = []
        for event_id, dataset in odds_response.items():
            try:
                event = event_dict[event_id]
                bet_dict = {}
                if dataset is not None and dataset['groups'] is not None:
                    for group in dataset['groups']:
                        for market in group['markets']:
                            for _, oddArray in market['odds'].items():
                                for odd in oddArray:
                                    odd_id = int(odd['id'].replace('LSK', ''))
                                    bet_dict[odd_id] = odd
                                
                for odd in event.odds.filter(parent__selected=True).all(): 
                    data_odd = bet_dict.get(odd.odd_id, None)
                    if data_odd is None: 
                        odd.locked = True
                        odds_to_update.append(odd)
                        continue
                    odds = data_odd["value"]
                    locked = data_odd["displayType"] != 'OPEN' or odds < 1
                    odd.movement = self.get_movement(odd.odd, odds)      
                    odd.odd = odds
                    odd.locked = locked
                    odds_to_update.append(odd)
            except Exception as ex:
                print(f"Exception in map_odds_selected Ifortuna: {str(ex)}.")
                continue                   
        
        return odds_to_update
                