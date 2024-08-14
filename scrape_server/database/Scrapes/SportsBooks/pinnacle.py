import asyncio
from ..dataclass_models import EventModel, OddModel
from ..scripts import get_existing_odds
from ...models import Odd, Event, Sport, Sportsbook, SportsbookMarket
from .scraper import Scraper
from datetime import datetime, timezone

class PinnacleScraper(Scraper):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        super().__init__(sportsbook, sports)
        self.headers = {'X-Api-Key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'}
        asyncio.run(self.get_labels())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_driver(self):
        return None
    
    def close_driver(self):
        pass
    
    async def get_labels(self): 
        url = 'https://guest.api.arcadia.pinnacle.com/0.1/labels?brandId=0'
        labels = await self.get(url, self.headers)
        sport_ids = self.get_sportids()
        selected_sport_ids = [sport.pk for sport in self.sports]
        keys = [key for key, item in sport_ids.items() if item in selected_sport_ids]
        self.labels = {sport_ids.get(label['sport']['id']): label['labels'] for label in labels if label['sport']['id'] in keys}

    async def gather_events(self, sports: list[Sport]):
        url = 'https://guest.api.arcadia.pinnacle.com/0.1/sports/live?brandId=0'
        live_sports = await self.get(url, self.headers)
        sport_ids = self.get_sportids()
        selected_sport_ids = [sport.pk for sport in sports]
        keys = [key for key, item in sport_ids.items() if item in selected_sport_ids]
        data = {sport_ids.get(sport['id']): f'https://guest.api.arcadia.pinnacle.com/0.1/sports/{sport['id']}/matchups/live?withSpecials=false&brandId=0' for sport in live_sports if sport['id'] in keys}
        
        return await self.gather_data(data, self.headers)

    async def gather_odds(self, events):
        data = {}
        for event in events:
            data[(event.event_id, event.sport_id)] = f'https://guest.api.arcadia.pinnacle.com/0.1/matchups/{event.event_id}//markets/related/straight'
        results = await self.gather_data(data, self.headers)
        
        return results
    
    def get_sportids(self) -> dict[int, int]: 
        sport_ids = {
            29: 1, #socker
            19: 2, #hokej
            33: 3, #tenis
            4: 4, #basketbal
            18: 5, #handball
            34: 6, #volejbal
            32: 7, #stolny tenis
            6: 8, # box
        }
        
        return sport_ids

    def map_events(self, data: dict[int, list]) -> list[EventModel]:
        events: list[EventModel] = []
        
        self.children = {}
        parent_ids = set()
        for sport_id, matches in data.items():
            try:
                for match in matches:
                    parent_id = int(match['parentId'])
                    if parent_id in parent_ids: 
                        self.children[parent_id][match['id']] = match
                        continue
                    parent_ids.add(parent_id)
                    self.children[parent_id] = {parent_id: match['parent'], match['id']: match}
                    parent = match['parent']
                    if len(parent['participants']) != 2: continue
                    time = self.get_time_from_start_time(parent['startTime'])
                    home = parent['participants'][0]['name']
                    away = parent['participants'][1]['name']
                    events.append(EventModel(
                        id=None, 
                        event_id=parent_id, 
                        time =time, 
                        home=home, 
                        away=away, 
                        is_default=self.sportsbook.is_default, 
                        selected=False, 
                        sportsbook_id=self.sportsbook.pk, 
                        sport_id=sport_id, 
                    ))
            except Exception as ex: 
                print(f"Exception in map_events Pinnacle: {str(ex)}.")
                continue  

        return events
    
    def map_odds(self, data: dict[tuple[int, int], list[object]]) -> tuple[list[OddModel], list[Odd]]:
        if all(element is None for element in data):
            raise Exception('No details retrieved.')
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        
        allowed_keys = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = get_existing_odds(self.sportsbook, False)
        for tple, dataset in data.items():
            parent_id = tple[0]
            sport_id = tple[1]
            labels = self.labels.get(sport_id)
            for bet in dataset:
                try:
                    if bet['key'] not in allowed_keys: continue
                    try:
                        matchup = self.children[parent_id][bet['matchupId']]
                    except: 
                        continue
                    parent = matchup['parent'] if 'parent' in matchup else matchup

                    existing_match_odds = existing_odds[parent_id]

                    home = parent['participants'][0]['name']
                    away = parent['participants'][1]['name']
                    matchup_home = matchup['participants'][0]['name']
                    matchup_away = matchup['participants'][1]['name']
                    participants_by_id = {participant['id']: participant for participant in matchup['participants'] if 'id' in participant}
                    label_obj = labels[bet['period']]
                    market_labels = {label['type']: label for label in label_obj['marketLabels']}
                    period_label = label_obj['periodLabel']['full']
                    match_description = market_labels[bet['type']]['full'] + ' - ' + period_label
                    if 'side' in bet:
                        description += ' ' + bet['side']
                    for index, price in enumerate(bet['prices']): 
                        odd_id = int(str(matchup['id']) + str(index))
                        odds = price['price']
                        locked = False
                        if odd_id in existing_match_odds: 
                            existing_odd = existing_match_odds[odd_id]
                            del existing_match_odds[odd_id]
                            existing_odd.movement = self.get_movement(existing_odd.odd, odds)
                            existing_odd.odd = odds
                            existing_odd.locked = locked
                            odds_to_update.append(existing_odd)
                            continue
                        description = ''
                        description += match_description
                        
                        if 'designation' in price:
                            description += ' ' + price['designation']
                        if 'participantId' in price:
                            description += ' ' + participants_by_id[price['participantId']]['name']
                        if 'points' in price: 
                            description +=  ' ' + price['points']

                        description = description.replace('home', matchup_home)
                        description = description.replace('away', matchup_away)
                        description = description.replace(home, "*1*")
                        description = description.replace(away, "*2*")
                        description = description.replace("  ", " ").replace("  ", " ").strip()
                        if 'Match ML Match *1*'==description: 
                            k=0
                            pass

                        odds_to_create.append(OddModel(
                            id = None,
                            odd_id = odd_id,
                            code = 0,
                            movement = 0,
                            odd = odds,
                            is_default = self.sportsbook.is_default,
                            selected = False,
                            locked = locked, 
                            event_id = parent_id,
                            sportsbook_id = self.sportsbook.pk,
                            description = description,
                            market_id = ""
                        ))        
                except Exception as ex:
                    print(f"Exception in map_odds Pinnacle: {str(ex)}.")
                    continue  

        return odds_to_create, odds_to_update       

    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        events_to_update: list[Event] = []
        events_to_delete: list[Event] = []
        for event in events:
            try:
                matches = event_response.get(event.sport.pk, None)
                match = next((match for match in matches if int(match['parentId']) == event.event_id), None)
                if match is None: 
                    events_to_delete.append(event)
                    continue
                time = self.get_time_from_start_time(match['parent']['startTime'])
                event.time = time    
                events_to_update.append(event)  
            except Exception as ex:
                print(f"Exception in map_events_selected Pinnacle: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def get_time_from_start_time(self, start_time: str) -> str:
        start_time = datetime.fromisoformat(start_time)
        current_time = datetime.now(timezone.utc)
        elapsed_time = current_time - start_time
        minutes = elapsed_time.total_seconds() // 60
        seconds = int(elapsed_time.total_seconds() % 60)
        formatted_time = f"{int(minutes)}:{seconds:02}"

        return formatted_time    
    
    def map_odds_selected(self, events: list[Event], odds_response: dict[tuple[int, int], list[object]]) -> list[Odd]:
        event_dict = {event.event_id: event for event in events}
        odds_to_update: list[Odd] = []
        for tple, dataset in odds_response.items():
            parent_id = tple[0]
            event = event_dict[parent_id]
            price_dict = {}
            for bet in dataset:
                for index, price in enumerate(bet['prices']):
                    price_dict[int(str(bet['matchupId']) + str(index))] = price
            
            for odd in event.odds.filter(selected=True).all(): 
                try:
                    price = price_dict.get(odd.odd_id, None)
                    if price is None: 
                        odd.locked = True
                        odds_to_update.append(odd)
                        continue
                    odd.movement = self.get_movement(odd.odd, price['price'])      
                    odd.odd = price['price']
                    odd.locked = False
                    odds_to_update.append(odd)
                    break
                except Exception as ex:
                    print(f"Exception in map_odds_selected Pinnacle: {str(ex)}.")
                    continue                   
        
        return odds_to_update
# add id asi nie je spravne