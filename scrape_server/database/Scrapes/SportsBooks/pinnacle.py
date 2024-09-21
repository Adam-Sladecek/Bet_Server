import asyncio
from ..dataclass_models import EventModel, OddModel
from ..scripts import get_existing_odds
from ...models import Odd, Event, Sport, Sportsbook, SportsbookMarket
from .scraper import Scraper

class PinnacleScraper(Scraper):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        super().__init__(sportsbook, sports)
        self.headers = {
            'X-Api-Key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R', 
            'Referer': 'https://www.pinnacle.bet/'
        }
        self.designations = []
        self.types = []
        self.subtypes = { 
            'home': 'team1',
            'away': 'team2'
        }
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
        self.available_sport_ids = [sport['id'] for sport in live_sports if sport['id'] in keys]
        data = {sport_ids.get(id): f'https://guest.api.arcadia.pinnacle.com/0.1/sports/{id}/matchups/live?withSpecials=false&brandId=0' for id in self.available_sport_ids}
        
        return await self.gather_data(data, self.headers)

    async def gather_odds(self, events):
        data = {}
        for event in events:
            data[(event.event_id, event.sport_id)] = f'https://guest.api.arcadia.pinnacle.com/0.1/matchups/{event.event_id}//markets/related/straight'
        results = await self.gather_data(data, self.headers)

        # sport_ids = self.get_sportids()
        # for id in self.available_sport_ids:
        #     data[sport_ids.get(id)] = f'https://guest.api.arcadia.pinnacle.com/0.1/sports/{id}/markets/live/straight?primaryOnly=false&withSpecials=false'
        # results = await self.gather_data(data, self.headers)
        
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
                        self.children[match['id']] = match
                        continue
                    parent_ids.add(parent_id)
                    self.children[match['id']] = match
                    parent = match['parent']
                    if parent is None: continue
                    if len(parent['participants']) != 2: continue
                    time = self.get_time_from_mach(match)
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
                        available_sportsbooks=[],
                        odd_count=0,
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
        existing_odds = get_existing_odds(self.sportsbook)
        mapped_data = {}
        for tple, dataset in data.items():
            if not isinstance(dataset, list): continue
            parent_id = tple[0]
            sport_id = tple[1]
            mapped_data[parent_id] = (sport_id, [bet for bet in dataset if (bet['key'] in allowed_keys or bet['type'] in allowed_keys) and "status" in bet and bet['status']=="open"])
        
        used_descriptions = {}
        for match_id, matchup in self.children.items():
            try:
                parent_id = int(matchup['parentId'])
                parent = matchup['parent']
                sport_id, bets = mapped_data[parent_id]
                if parent_id not in used_descriptions:
                    used_descriptions[parent['id']] = set()
            except: continue
            try:
                labels = self.labels.get(sport_id)
                match_bet = next((bet for bet in bets if int(bet['matchupId']) == match_id), None)
                if match_bet is None: continue
                existing_match_odds = existing_odds[parent_id]
                for odd in existing_match_odds.values():
                    used_descriptions[parent_id].add(odd.opportunity.description)

                home = parent['participants'][0]['name']
                away = parent['participants'][1]['name']
                matchup_home = matchup['participants'][0]['name']
                matchup_away = matchup['participants'][1]['name']
                participants_by_id = {participant['id']: participant for participant in matchup['participants'] if 'id' in participant}
                label_obj = labels[match_bet['period']]
                match_description = ''
                for label in [lbl for lbl in label_obj['marketLabels'] if lbl['type'] == match_bet['type']]: 
                    if 'side' in match_bet and 'subType' in label:
                        if label['subType'] == self.subtypes[match_bet['side']]:
                            match_description += label['full']
                            break
                        continue    
                    match_description += label['full']  
                    break

                period_label = label_obj['periodLabel']['full']
                match_description += f' - {period_label} - '

                line_odds = [self.american_to_decimal(price['price']) for price in match_bet['prices']]
                impl_prob = sum(1 / odd for odd in line_odds)
                true_odds = lambda index: round(line_odds[index] * impl_prob, 3)

                for index, price in enumerate(match_bet['prices']): 
                    odd_id = self.get_odd_id(match_bet, price, index)
                    odds = true_odds(index)
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
                    
                    if description in used_descriptions[parent_id]: continue
                    used_descriptions[parent_id].add(description)

                    odds_to_create.append(OddModel(
                        id = None,
                        odd_id = odd_id,
                        code = 0,
                        movement = 1,
                        odd = odds,
                        is_default = self.sportsbook.is_default,
                        selected = False,
                        locked = locked, 
                        event_id = parent['id'],
                        sportsbook_id = self.sportsbook.pk,
                        description = description,
                        market_id = ""
                    ))        
            except Exception as ex:
                print(f"Exception in map_odds Pinnacle: {str(ex)}.")
                continue  

        return odds_to_create, odds_to_update       
    
    def american_to_decimal(self, american_odds: int): 
        if american_odds > 0:
            decimal_odds = (american_odds / 100) + 1
        else:
            decimal_odds = (100 / abs(american_odds)) + 1
        return round(decimal_odds, 3)
    
    def get_odd_id(self, bet, price, index) -> int:
        odd_id = int(str(bet['matchupId']) + str(index))
        if 'period' in bet: 
            odd_id = int(str(odd_id) + str(bet['period']))
        if 'type' in bet: 
            if bet['type'] not in self.types: 
                self.types.append(bet['type'])
            odd_id = int(str(odd_id) + str(self.types.index(bet['type'])))    
        if 'designation' in price: 
            if price['designation'] not in self.designations: 
                self.designations.append(price['designation'])
            odd_id = int(str(odd_id) + str(self.designations.index(price['designation'])))
        if 'points' in price:
            odd_id = int(str(odd_id) + str(price['points']).replace('.', '').replace('-', ''))
        
        return odd_id    

    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        events_to_update: list[Event] = []
        events_to_delete: list[Event] = []
        self.children = {}
        for event in events:
            try:
                matches = event_response.get(event.sport.pk, None)
                matches = [match for match in matches if int(match['parentId']) == event.event_id]
                if len(matches) == 0: 
                    events_to_delete.append(event)
                    continue
                first_match = matches[0]
                time = self.get_time_from_mach(first_match)
                event.time = time  
                for match in matches:
                    self.children[match['id']] = match
                events_to_update.append(event)  
            except Exception as ex:
                print(f"Exception in map_events_selected Pinnacle: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def get_time_from_mach(self, match) -> str:
        if 'state' in match and 'minutes' in match['state']:
            return str(match['state']['minutes']) + "'"
        return ''    
    
    def map_odds_selected(self, events: list[Event], odds_response: dict[int, list[object]]) -> list[Odd]:
        odds_to_update: list[Odd] = []
        allowed_keys = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        for event in events:
            price_dict = {}
            bets_unfiltered = odds_response[(event.event_id, event.sport.pk)]
            if not isinstance(bets_unfiltered, list): continue
            bets = [bet for bet in bets_unfiltered if (bet['key'] in allowed_keys or bet['type'] in allowed_keys) and "status" in bet and bet['status']=="open"]
            for bet in bets:
                if bet['matchupId'] not in self.children: continue
                matchup = self.children[bet['matchupId']]
                parent = matchup['parent']
                if parent['id'] != event.event_id: continue
                line_odds = [self.american_to_decimal(price['price']) for price in bet['prices']]
                impl_prob = sum(1 / odd for odd in line_odds)
                for index, price in enumerate(bet['prices']):
                    odd_id = self.get_odd_id(bet, price, index)
                    price_dict[odd_id] = (price, bool(bet['isAlternate']), impl_prob)

            for odd in event.odds.filter(selected=True).all(): 
                try:
                    tple = price_dict.get(odd.odd_id, None)
                    if tple is None or tple[1]: 
                        odd.locked = True
                        odds_to_update.append(odd)
                        continue
                    price = tple[0]
                    isAlternate = tple[1]
                    impl_prob = tple[2]
                    odds = self.american_to_decimal(price['price'])
                    true_odds = round(odds * impl_prob, 3)
                    odd.movement = self.get_movement(odd.odd, true_odds)      
                    odd.odd = true_odds
                    odd.locked = False
                    odds_to_update.append(odd)
                except Exception as ex:
                    print(f"Exception in map_odds_selected Pinnacle: {str(ex)}.")
                    continue          
        
        return odds_to_update