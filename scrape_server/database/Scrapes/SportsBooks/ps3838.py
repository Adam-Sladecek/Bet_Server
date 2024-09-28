import asyncio
from ..dataclass_models import EventModel, OddModel
from ..scripts import get_existing_odds
from ...models import Odd, Event, Sport, Sportsbook, SportsbookMarket
from .scraper import Scraper
from..ps3838_dataclasses import SportPS3838, FixturePS3838
import json
from ..scripts import update_events, update_odds, get_selected_events, update_selected_events, update_selected_odds

class PS3838Scraper(Scraper):
    def __init__(self, sportsbook: Sportsbook, sports: list[Sport]):
        super().__init__(sportsbook, sports)
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Basic QklBMDAwMzFGNDpCcmVzdG92YW55MTIz'
        }
        selected_sport_ids = [sport.pk for sport in self.sports]
        self.fixture_since = {id: None for id in selected_sport_ids}
        self.fixture_settled_since = {id: None for id in selected_sport_ids}
        self.odds_since = {id: None for id in selected_sport_ids}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_driver(self):
        return None

    def close_driver(self):
        pass

    #import all: get all events -> add all to db -> get settled events -> store since parameters
    #get data: get increment live events -> get increment settled events -
    def import_all_data(self):
        sport_ids = self.get_sportids()
        selected_sport_ids = [sport.pk for sport in self.sports]
        sb_sport_ids= [key for key, item in sport_ids.items() if item in selected_sport_ids]
        loop = self.get_loop()
        event_response = loop.run_until_complete(self.gather_events(sb_sport_ids))
        events = self.map_events(event_response)
        update_events(events, self.sportsbook)
        # add or update
        event_settled_response = loop.run_until_complete(self.gather_settled_events(sb_sport_ids))
        # delete redundant events
        events_ids = [event.pk for event in events if event.pk is not None]
        odds_response = loop.run_until_complete(self.gather_odds(events))
        odds_to_create, odds_to_update = self.map_odds(odds_response)
        update_odds(odds_to_create, odds_to_update, self.sportsbook)

    def get_data(self):
        events, sport_ids = get_selected_events(self.sportsbook)
        if len(events) == 0: return
        sports = [sport for sport in self.sports if sport.pk in sport_ids]
        loop = self.get_loop()
        event_response = loop.run_until_complete(self.gather_events(sports))
        events_to_update, events_to_delete = self.map_events_selected(events, event_response)
        update_selected_events(events_to_update, events_to_delete)
        events = [event for event in events if event.pk is not None]
        odds_response = loop.run_until_complete(self.gather_odds(events))
        odds_to_update = self.map_odds_selected(events, odds_response)
        update_selected_odds(odds_to_update)

    async def gather_events(self, sport_ids, league_ids=[], event_ids=[]):
        url = 'https://api.ps3838.com/v3/fixtures'
        internal_sport_ids = self.get_sportids()
        result = {}
        for id in sport_ids:
            params = {'isLive': 1, 'sportId': id}
            internal_sport_id = internal_sport_ids.get(id)
            since = self.fixture_since.get(internal_sport_id)
            if since is not None:
                params['since'] = since

            if len(league_ids) > 0:
                params['leagueIds'] = ','.join(map(str, league_ids))

            if len(event_ids) > 0:
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

    async def gather_odds(self, sport_ids, event_ids=[], league_ids=[]):
        url = 'https://api.ps3838.com/v3/odds'
        internal_sport_ids = self.get_sportids()
        result = {}
        for id in sport_ids:
            internal_sport_id = internal_sport_ids.get(id)
            params = {'sportId': id, 'oddsFormat': 'Decimal', 'isLive': 1}
            since = self.odds_since.get(internal_sport_id)
            if since is not None:
                params['since'] = since

            if len(league_ids) > 0:
                params['leagueIds'] = ','.join(map(str, league_ids))

            if len(event_ids) > 0:
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
            if model is None: continue
            event_dataclasses = FixturePS3838.dataclass_from_model(model)
            for league in event_dataclasses.league:
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

    def map_odds(self, data: dict[tuple[int, int], list[object]]) -> tuple[list[OddModel], list[Odd]]:
        pass

    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        pass

    def map_odds_selected(self, events: list[Event], odds_response: dict[int, list[object]]) -> list[Odd]:
        pass