import asyncio
from decimal import Decimal
from .scraper import Scraper
from ..dataclass_models import EventModel, OddModel
from ..scripts import get_existing_odds, update_events, update_odds, get_selected_events
from ...models import Odd, Sport, Event
from django.db import transaction

class NikeScraper(Scraper):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass    

    async def gather_events(self, sports: list[Sport]):
        data = {sport.pk: f'https://push.nike.sk/snapshot?format=v2&path=/n1/overview/{getattr(self.sportsbook, sport.url)}/tournaments/' for sport in sports}
        return await self.gather_data(data)

    async def gather_odds(self, events: list[Event]):
        data = {}
        for index, event in enumerate(events):
            data[index] = f'https://push.nike.sk/snapshot?format=v2&path=/n1/match/{event.event_id}/bets/portal/'
        results = await self.gather_data(data)
        return results.values()
    
    def map_events(self, data: dict[int, object]) -> list[EventModel]:
        self.events: list[EventModel] = []
        for sport_id, result in data.items():
            try:
                matches = result[0][1]['matches']
                for match in matches:
                    event_id = int(match['id'])
                    time = self.get_time_from_match(match)
                    home = match['home']['sk']
                    away = match['away']['sk']
                    self.events.append(EventModel(
                        id=None, 
                        event_id=event_id, 
                        time =time, 
                        home=home, 
                        away=away, 
                        is_default=self.sportsbook.is_default, 
                        selected=False, 
                        sportsbook_id=self.sportsbook.pk, 
                        sport_id=sport_id, 
                        parent_id=None
                    ))
            except Exception as ex: 
                print(f"Exception in map_events Nike: {str(ex)}.")
                continue    
    
    def map_odds(self, data: list[object]) -> tuple[list[OddModel], list[Odd], list[Odd]]:
        if all(element is None for element in data):
            raise Exception('No details retrieved.')
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        forbidden_market_ids = ['9440', '8223', '6389', '10766', '10767', '10783',
                                '8474', '10782', '9278', '9990', '9993', '9994']
        forbidden_set = set(forbidden_market_ids)
        existing_odds = get_existing_odds(self.sportsbook, True)
        for dataset in data:
            for bet in dataset[0][1]['bets']:
                try:
                    if bet['marketId'] in forbidden_set: continue
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
                            existing_odd.odd = odd["odds"]
                            existing_odd.locked = locked
                            odds_to_update.append(existing_odd)
                            continue
                        
                        description = bet["header"]['sk'] + " " + odd["name"]['sk']
                        description = description.replace(home, "*1*")
                        if away is not None:
                            description = description.replace(away, "*2*")
                        description = description.replace("  ", " ")
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
                            parent_id=None, 
                            market_id=bet['marketId']
                        ))        
                except Exception as ex:
                    print(f"Exception in map_odds Nike: {str(ex)}.")
                    continue     
        return odds_to_create, odds_to_update       

    def get_driver(self):
        return None
    
    def map_events_selected(self, events: list[Event], event_response: dict[int, object]):
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
                print(f"Exception in map_events_selected Nike: {str(ex)}.")
                continue       
        with transaction.atomic():
            for event in events_to_delete: 
                event.delete()
            Event.objects.bulk_update(events_to_update, ['time'])

    def get_time_from_match(self, match):
        time = match['timer']['currentPeriod']['sk']
        if 'timestamp' in match['timer']:
            countdown = bool(match['timer']['countDown'])
            timestamp = match['timer']['timestamp']
            if 'matchSeconds' in match['timer']:
                seconds = match['timer']['matchSeconds']
                timestamp -= seconds*1000
            converted_time = self.convert_timestamp_to_time_string(timestamp) if not countdown else self.convert_seconds_to_time_string(seconds)
            time += f' {converted_time}'
        return time    
    
    def map_odds_selected(self, events: list[Event], odds_response: list[object]):
        event_dict = {event.event_id: event for event in events}
        odds_to_update: list[Odd] = []
        for data in odds_response:
            try:
                event_id = int(data[0][1]['matchId'])
                event = event_dict[event_id]
                if event.pk is None: continue
                bet_dict = {int(bet['id']): bet for bet in data[0][1]['bets']}
                for odd in event.odds.filter(selected=True).all(): 
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
                print(f"Exception in map_odds_selected Nike: {str(ex)}.")
                continue                   
        with transaction.atomic():
            Odd.objects.bulk_update(odds_to_update, ['odd', 'locked', 'movement'])
                
    def get_data(self):
        try:
            events, sport_ids = get_selected_events(self.sportsbook)
            if len(events) == 0: return
            sports = [sport for sport in self.sports if sport.pk in sport_ids]
            event_response = asyncio.run(self.gather_events(sports))
            self.map_events_selected(events, event_response)
            odds_response = asyncio.run(self.gather_odds(events))
            self.map_odds_selected(events, odds_response)

        except Exception as ex:
            print(f"Failed to update Nike odds. Exception: {str(ex)}.")

    def import_all_data(self):
        try:
            event_response = asyncio.run(self.gather_events(self.sports))
            self.map_events(event_response)
            update_events(self.events, self.sportsbook)    
            odds_response = asyncio.run(self.gather_odds(self.events))
            odds_to_create, odds_to_update = self.map_odds(odds_response)
            update_odds(odds_to_create, odds_to_update, self.sportsbook)
        except Exception as ex:
            print(f"Failed import Nike data. Exception: {str(ex)}.")
    