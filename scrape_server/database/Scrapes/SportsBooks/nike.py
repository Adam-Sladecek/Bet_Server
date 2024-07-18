import asyncio
from decimal import Decimal
from .scraper import Scraper
from ..dataclass_models import EventModel, OddModel, RequestModel
from ..scripts import get_existing_odds, update_events, update_odds
from ...models import Odd

class NikeScraper(Scraper):
    def __init__(self, requests: list[RequestModel]):
        self.requests = requests
        self.events: list[EventModel] = []

    async def gather_events(self):
        data = [(f'https://push.nike.sk/snapshot?format=v2&path=/n1/overview/{request.url}/tournaments/', request) for request in self.requests]
        return await self.gather_data(data)

    async def gather_odds(self):
        data = []
        for event in self.events:
            data.append((f'https://push.nike.sk/snapshot?format=v2&path=/n1/match/{event.event_id}/bets/portal/', None))
        results = await self.gather_data(data)
        return [result[0] for result in results]
    
    def map_events(self, data: list[tuple[object, RequestModel]]) -> list[EventModel]:
        for result, request in data:
            try:
                matches = result[0][1]['matches']
                for match in matches:
                    event_id = int(match['id'])
                    time = match['timer']['currentPeriod']['sk']
                    if 'timestamp' in match['timer']:
                        timestamp = match['timer']['timestamp']
                        if 'matchSeconds' in match['timer']:
                            seconds = match['timer']['matchSeconds']
                            timestamp -= seconds*1000
                        converted_time = self.convert_timestamp_to_time_string(timestamp)
                        time += f' {converted_time}'
                    home = match['home']['sk']
                    away = match['away']['sk']
                    self.events.append(EventModel(
                        id=None, 
                        event_id=event_id, 
                        time =time, 
                        home=home, 
                        away=away, 
                        is_default=self.requests[0].is_default, 
                        selected=False, 
                        sportsbook_id=request.sportsbook_id, 
                        sport_id=request.sport_id, 
                        parent_id=None
                    ))
            except Exception as ex: 
                print(f"Exception in map_events Nike: {str(ex)}.")
                continue    
    
    def map_odds(self, data) -> tuple[list[OddModel], list[Odd], list[Odd]]:
        if all(element is None for element in data):
            raise Exception('No details retrieved.')
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        forbidden_market_ids = ['9440', '8223', '6389', '10766', '10767', '10783',
                                '8474', '10782', '9278']
        forbidden_set = set(forbidden_market_ids)
        existing_odds = get_existing_odds(self.requests[0].sportsbook_id, True)
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
                            odd = odd["odds"],
                            is_default=self.requests[0].is_default,
                            selected=False,
                            locked = locked, 
                            event_id = event_id,
                            sportsbook_id=self.requests[0].sportsbook_id,
                            description = description,
                            parent_id=None, 
                            market_id=bet['marketId']
                        ))        
                except Exception as ex:
                    print(f"Exception in map_odds Nike: {str(ex)}.")
                    continue     
        return odds_to_create, odds_to_update       

    # def get_data(self):
    #     try:
    #         order = ''
    #         counter = 0
    #         while True:
    #             if counter >= 100:
    #                 print('Nike too many requests.')
    #                 break
    #             resultjson = asyncio.run(self.gather_events(order)) 
    #             self.map_events(resultjson)
    #             if not resultjson[0]['hasMoreBets']:
    #                 break
    #             order = '=' + str(int(resultjson[0]['maxBoxOrder']))
    #             counter += 1
    #         update_events(self.events, self.request.sport_id, self.request.sportsbook_id)    
    #         details_results = asyncio.run(self.gather_details())
    #         return self.map_odds(details_results)
    #     except Exception as ex:
    #         print(f"Failed to get Nike driver {str(ex)}.")
    #         return None, None, None

    def import_all_data(self):
        try:
            event_response = asyncio.run(self.gather_events())
            self.map_events(event_response)
            update_events(self.events, self.requests[0].sportsbook_id)    
            odds_response = asyncio.run(self.gather_odds())
            odds_to_create, odds_to_update = self.map_odds(odds_response)
            update_odds(odds_to_create, odds_to_update, self.requests[0].sportsbook_id)
        except Exception as ex:
            print(f"Failed import Nike data. Exception: {str(ex)}.")
    