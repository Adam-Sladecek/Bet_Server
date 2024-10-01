import asyncio
from ..dataclass_models import EventModel, OddModel
from ..scripts import get_existing_odds
from ...models import Odd, Event, Sport, Sportsbook, SportsbookMarket
from .scraper import Scraper
from..ps3838_dataclasses import FixturePS3838, PeriodPS3838
from ..scripts import update_events, update_odds, get_selected_events, delete_settled_events
from datetime import datetime, timezone

class PS3838Scraper(Scraper):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        super().__init__(sportsbook, sports)
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Basic QklBMDAwMzFGNDpCcmVzdG92YW55MTIz'
        }
        self.descriptions = {
            'moneyline': 'moneylineDescription',
        }
        selected_sport_ids = [sport.pk for sport in self.sports]
        sb_sport_ids= [key for key, item in self.get_sportids().items() if item in selected_sport_ids]
        self.fixture_since = {id: None for id in selected_sport_ids}
        self.fixture_settled_since = {id: None for id in selected_sport_ids}
        self.odds_since = {id: None for id in selected_sport_ids}
        asyncio.run(self.gather_periods(sb_sport_ids))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_driver(self):
        return None

    def close_driver(self):
        pass
    
    def import_all_data(self):
        sport_ids = self.get_sportids()
        selected_sport_ids = [sport.pk for sport in self.sports]
        sb_sport_ids= [key for key, item in sport_ids.items() if item in selected_sport_ids]
        loop = self.get_loop()
        event_response = loop.run_until_complete(self.gather_events(sb_sport_ids))
        events = self.map_events(event_response)
        update_events(events, self.sportsbook, False)

        event_settled_response = loop.run_until_complete(self.gather_settled_events(sb_sport_ids))
        settled_event_ids = self.get_settled_event_ids(event_settled_response)
        delete_settled_events(settled_event_ids, self.sportsbook)
        events = [event for event in events if event.event_id not in settled_event_ids]

        event_id_dict = {}
        league_id_dict = {}
        for event in events:
            if event.sport_id not in event_id_dict: event_id_dict[event.sport_id] = set()
            if event.sport_id not in league_id_dict: league_id_dict[event.sport_id] = set()
            event_id_dict[event.sport_id].add(event.event_id)
            league_id_dict[event.sport_id].add(event.league_id)

        odds_response_dict = loop.run_until_complete(self.gather_odds(sb_sport_ids, event_id_dict, league_id_dict))
        odds_to_create, odds_to_update = self.map_odds(odds_response_dict)
        update_odds(odds_to_create, odds_to_update, self.sportsbook)

    def get_data(self):
        events, sport_ids = get_selected_events(self.sportsbook)
        if len(events) == 0: return
        event_id_dict = {}
        league_id_dict = {}
        for event in events:
            if event.sport.pk not in event_id_dict: event_id_dict[event.sport.pk] = set()
            if event.sport.pk not in league_id_dict: league_id_dict[event.sport.pk] = set()
            event_id_dict[event.sport.pk].add(event.event_id)
            league_id_dict[event.sport.pk].add(event.league_id)

        sb_sport_ids= [key for key, item in self.get_sportids().items() if item in sport_ids]
        loop = self.get_loop()
        odds_response_dict = loop.run_until_complete(self.gather_odds(sb_sport_ids, event_id_dict, league_id_dict))
        odds_to_create, odds_to_update = self.map_odds(odds_response_dict)
        update_odds(odds_to_create, odds_to_update, self.sportsbook)

    def get_settled_event_ids(self, response: dict) -> list[int]:
        result = []
        for sport_id, model in response.items():
            if model is None or 'last' not in model: continue
            self.fixture_settled_since[sport_id] = model['last']
            for league in model['leagues']:
                for event in league['events']:
                    result.append(event['id'])

        return result
    
    async def gather_periods(self, sport_ids: list[int]): 
        self.periods = {}
        url = 'https://api.ps3838.com/v1/periods'
        internal_sport_ids = self.get_sportids()
        for sport_id in sport_ids: 
            params = {'sportId': sport_id}
            response = await self.get(url, self.headers, params)
            mapped_periods = PeriodPS3838.dataclass_list_from_model(response)
            self.periods[internal_sport_ids[sport_id]] = {period.number: period for period in mapped_periods}
            
    async def gather_events(self, sport_ids, event_id_dict={}, league_id_dict={}):
        url = 'https://api.ps3838.com/v3/fixtures'
        internal_sport_ids = self.get_sportids()
        result = {}
        for id in sport_ids:
            params = {'isLive': 1, 'sportId': id}
            internal_sport_id = internal_sport_ids.get(id)
            since = self.fixture_since.get(internal_sport_id)
            if since is not None:
                params['since'] = since

            league_ids = league_id_dict.get(internal_sport_id)
            if league_ids is not None and len(league_ids) > 0:
                params['leagueIds'] = ','.join(map(str, league_ids))

            event_ids = event_id_dict.get(internal_sport_id)
            if event_ids is not None and len(event_ids) > 0:
                params['eventIds'] = ','.join(map(str, event_ids))

            response = await self.get(url, self.headers, params)
            result[internal_sport_id] = response
        
        return result

    async def gather_settled_events(self, sport_ids):
        url = 'https://api.ps3838.com/v3/fixtures/settled'
        internal_sport_ids = self.get_sportids()
        result = {}
        for id in sport_ids:
            internal_sport_id = internal_sport_ids.get(id)
            params = {'sportId': id}
            since = self.fixture_settled_since.get(internal_sport_id)
            if since is not None:
                params['since'] = since
            
            response = await self.get(url, self.headers, params)
            result[internal_sport_id] = response

        return result

    async def gather_odds(self, sport_ids, event_id_dict={}, league_id_dict={}):
        url = 'https://api.ps3838.com/v3/odds'
        internal_sport_ids = self.get_sportids()
        result = {}
        for id in sport_ids:
            internal_sport_id = internal_sport_ids.get(id)
            params = {'sportId': id, 'oddsFormat': 'Decimal', 'isLive': 1}
            since = self.odds_since.get(internal_sport_id)
            if since is not None:
                params['since'] = since

            league_ids = league_id_dict.get(internal_sport_id)
            if league_ids is not None and len(league_ids) > 0:
                params['leagueIds'] = ','.join(map(str, league_ids))

            event_ids = event_id_dict.get(internal_sport_id)
            if event_ids is not None and len(event_ids) > 0:
                params['eventIds'] = ','.join(map(str, event_ids))

            response = await self.get(url, self.headers, params)
            result[internal_sport_id] = response

        return result

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

    def map_events(self, data: dict[int, object]) -> list[EventModel]:
        events: list[EventModel] = []
        for sport_id, model in data.items():
            if model is None or 'last' not in model: 
                continue
            fixture = FixturePS3838.dataclass_from_model(model)
            self.fixture_since[sport_id] = fixture.last
            for league in fixture.league:
                for event in league.events:
                    events.append(
                        EventModel(
                            id=None,
                            event_id=event.id,
                            league_id=league.id,
                            time ='',
                            home=event.home,
                            away=event.away,
                            is_default=self.sportsbook.is_default,
                            selected=False,
                            sportsbook_id=self.sportsbook.pk,
                            sport_id=sport_id,
                            available_sportsbooks=[],
                            odd_count=0,
                        ))
        return events

    def map_odds(self, data: dict[int, object]) -> tuple[list[OddModel], list[Odd]]:
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        allowed_keys = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = get_existing_odds(self.sportsbook)
        for sport_id, dataset in data.items():
            try:
                if dataset is None or 'last' not in dataset: continue
                sport_periods = self.periods[sport_id]
                self.odds_since[sport_id] = dataset['last']
                for league in dataset['leagues']: 
                    for event in league['events']: 
                        existing_match_odds = existing_odds[event['id']]
                        for period in event['periods']:
                            line_id=period['lineId']
                            label = sport_periods[period['number']]
                            locked = period['status'] != 1 or self.is_in_past(period['cutoff'])
                            for all_key in allowed_keys:
                                if all_key not in period or not isinstance(period[all_key], dict): continue
                                enumerator = 0
                                for key, odds in period[all_key].items():
                                    odd_id = int(str(line_id) + str(enumerator))
                                    enumerator +=1
                                    if odd_id in existing_match_odds: 
                                        existing_odd = existing_match_odds[odd_id]
                                        del existing_match_odds[odd_id]
                                        existing_odd.movement = self.get_movement(existing_odd.odd, odds)
                                        existing_odd.odd = odds
                                        existing_odd.locked = locked
                                        odds_to_update.append(existing_odd)
                                        continue
                                    
                                    # description = f'{label[self.descriptions[all_key]]} - {key}'
                                    description = f'{label.moneylineDescription} - {key}'
                                    description = description.replace('home', "*1*")
                                    description = description.replace('away', "*2*")
                                    description = description.replace("  ", " ").replace("  ", " ").strip()
                                    odds_to_create.append(OddModel(
                                        id = None,
                                        odd_id = odd_id,
                                        code = 0,
                                        movement = 1,
                                        odd = odds,
                                        is_default = self.sportsbook.is_default,
                                        selected = False,
                                        locked = locked, 
                                        event_id = event['id'],
                                        sportsbook_id = self.sportsbook.pk,
                                        description = description,
                                        market_id = ""
                                    ))          
            except Exception as ex:
                print(f"Exception in map_odds Ps3838: {str(ex)}.")
                continue  

        return odds_to_create, odds_to_update       

    def is_in_past(self, date_time: str) -> bool: 
        try:
            date = datetime.strptime(date_time, "%Y-%m-%dT%H:%M:%SZ")
            now = datetime.now(timezone.utc)
            return date <= now
        except: 
            return True
        
    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        pass

    def map_odds_selected(self, events: list[Event], odds_response: dict[int, list[object]]) -> list[Odd]:
        pass