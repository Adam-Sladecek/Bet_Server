from .scraper import Scraper
from ..dataclass_models import EventModel, OddModel
from ..scripts import get_existing_odds
from ...models import Odd, Sport, Event, SportsbookMarket

class IFortunaScraper(Scraper):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass    

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
            data[event.event_id] = f'https://push.nike.sk/snapshot?format=v2&path=/n1/match/{event.event_id}/bets/portal/'
        results = await self.gather_data(data, {})
        
        return results.values()
    
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
                print(f"Exception in map_events IFortuna: {str(ex)}.")
                continue  

        return events
    
    def map_odds(self, data: list[object]) -> tuple[list[OddModel], list[Odd]]:
        if all(element is None for element in data):
            raise Exception('No details retrieved.')
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        
        allowed_market_ids = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = get_existing_odds(self.sportsbook, True)
        for dataset in data:
            for bet in dataset[0][1]['bets']:
                try:
                    if bet['marketId'] not in allowed_market_ids: continue
                    odd_id = int(bet['id'])
                    home = bet["participants"][0]['sk']
                    away = bet["participants"][1]['sk'] if len(bet["participants"]) == 2 else None
                    event_id = int(bet['matchId'])
                    existing_match_odds = existing_odds[event_id]
                    for odd in bet['selections']: 
                        code = odd["code"]
                        locked = odd["locked"] or not odd["enabled"]
                        if (odd_id, code) in existing_match_odds: 
                            existing_odd = existing_match_odds[(odd_id, code)]
                            del existing_match_odds[(odd_id, code)]
                            existing_odd.movement = self.get_movement(existing_odd.odd, odd["odds"])
                            existing_odd.odd = odd["odds"]
                            existing_odd.locked = locked
                            odds_to_update.append(existing_odd)
                            continue
                        
                        description = bet["header"]['sk'] + " " + odd["name"]['sk']
                        description = description.replace(home, "*1*")
                        if away is not None:
                            description = description.replace(away, "*2*")
                        description = description.replace("  ", " ").replace("  ", " ").strip()
                        odds_to_create.append(OddModel(
                            id=None,
                            odd_id = odd_id,
                            code= code,
                            movement= 0,
                            odd = odd["odds"],
                            is_default=self.sportsbook.is_default,
                            selected= False,
                            locked = locked, 
                            event_id = event_id,
                            sportsbook_id=self.sportsbook.pk,
                            description = description,
                            market_id=bet['marketId']
                        ))        
                except Exception as ex:
                    print(f"Exception in map_odds IFortuna: {str(ex)}.")
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
                matches = result[0][1]['matches']
                match = next((match for match in matches if int(match['id']) == event.event_id), None)
                if match is None: 
                    events_to_delete.append(event)
                    continue
                time = self.get_time_from_match(match)
                event.time = time    
                events_to_update.append(event)  
            except Exception as ex:
                print(f"Exception in map_events_selected IFortuna: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def get_time_from_match(self, match) -> str:
        time = match['timer']['currentPeriod']['sk'] if 'currentPeriod' in match['timer'] else ''
        if 'timestamp' in match['timer']:
            countdown = bool(match['timer']['countDown'])
            timestamp = match['timer']['timestamp']
            if 'matchSeconds' in match['timer']:
                seconds = match['timer']['matchSeconds']
                timestamp -= seconds*1000
            converted_time = self.convert_timestamp_to_time_string(timestamp) if not countdown else self.convert_seconds_to_time_string(seconds)
            time += f' {converted_time}'

        return time

    def map_odds_selected(self, events: list[Event], odds_response: list[object]) -> list[Odd]:
        event_dict = {event.event_id: event for event in events}
        odds_to_update: list[Odd] = []
        for data in odds_response:
            try:
                event_id = int(data[0][1]['matchId'])
                event = event_dict[event_id]
                bet_dict = {int(bet['id']): bet for bet in data[0][1]['bets']}
                for odd in event.odds.filter(parent__selected=True).all(): 
                    data_bet = bet_dict.get(odd.odd_id, None)
                    if data_bet is None: 
                        odd.locked = True
                        odds_to_update.append(odd)
                        continue
                    for data_odd in data_bet['selections']:
                        code = data_odd["code"]
                        if odd.code == code: 
                            odd.movement = self.get_movement(odd.odd, data_odd["odds"])      
                            odd.odd = data_odd["odds"]
                            odd.locked = data_odd["locked"] or not data_odd["enabled"]
                            odds_to_update.append(odd)
                            break
            except Exception as ex:
                print(f"Exception in map_odds_selected IFortuna: {str(ex)}.")
                continue                   
        
        return odds_to_update
                