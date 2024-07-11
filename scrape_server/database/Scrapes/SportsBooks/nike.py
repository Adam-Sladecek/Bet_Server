import asyncio
from decimal import Decimal
from .scraper import Scraper
from ..dataclass_models import EventModel, OddModel, RequestModel
# from ..scripts import get_existing_odds, update_events
from ..scripts import update_events
from ...models import Odd

class NikeScraper(Scraper):
    def __init__(self, requests: list[RequestModel]):
        self.requests = requests
        self.events: list[EventModel] = []

    async def gather_events(self):
        data = [(f'https://push.nike.sk/snapshot?format=v2&path=/n1/overview/{request.url}/tournaments/', request) for request in self.requests]
        return await self.gather_data(data)

    # async def gather_details(self):
    #     urls = []
    #     for box_id, sport_event_id in self.detail_ids:
    #         if box_id is None or sport_event_id is None: continue
    #         urls.append(f'https://www.nike.sk/api-gw/nikeone/v1/boxes/extended/sport-event-id?boxId={box_id}&sportEventId={sport_event_id}')
        # return await self.gather_data(urls)
    
    def map_events(self, data: list[tuple[object, RequestModel]]) -> list[EventModel]:
        for result, request in data:
            try:
                matches = result[0][1]['matches']
                for match in matches:
                    id = int(match['id'])
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
                    self.events.append(EventModel(id, time, home, away, request.sport_id, request.sportsbook_id, False))
            except Exception as ex: 
                print(f"Exception in map_events Nike: {str(ex)}.")
                continue    
    
    # def map_odds(self, details) -> tuple[list[OddModel], list[Odd], list[Odd]]:
    #     if all(element is None for element in details):
    #         raise Exception('No details retrieved.')
    #     odds_to_create: list[OddModel] = []
    #     odds_to_update: list[Odd] = []
    #     odds_to_delete: list[Odd] = []
    #     forbidden_market_ids = ['5409', '5664', '5672', '5232', '10824']
    #     existing_odds = get_existing_odds(self.request.sportsbook_id, self.request.sport_id, True)
    #     for detail in details:
    #         try:
    #             name1, name2 = detail["bets"][0]["participants"]
    #             event_id = int(detail["sportEvents"][0]["sportEventId"])
    #             existing_match_odds = existing_odds[event_id]
    #         except:
    #             continue    
    #         for bet in detail["bets"]:
    #             market_id = bet["marketId"]
    #             if bet["headerDetail"] == "Superšanca": continue
    #             if market_id in forbidden_market_ids: continue
    #             bet_id = bet["betId"]
    #             bet_order = int(bet["betOrder"])
    #             if self.request.sport_id in [8,9] and bet["headerDetail"] in ["Zápas", "1. polčas", "2. polčas", "1.tretina", "2.tretina", "3.tretina"]: 
    #                 array = bet["selectionGrid"][0] + bet["selectionGrid"][1]
    #             else: 
    #                 if bet["rows"] != 1 or len(bet["selectionGrid"][0]) != 2: continue
    #                 array = bet["selectionGrid"][0]    
    #             for odd in array: 
    #                 try:
    #                     if not odd["enabled"] or odd["locked"] or "tip" not in odd: continue
    #                 except Exception as ex:
    #                     continue

    #                 tip = odd["tip"]
    #                 if (int(bet_id), tip) in existing_match_odds: 
    #                     existing_odd = existing_match_odds[(int(bet_id), tip)]
    #                     del existing_match_odds[(int(bet_id), tip)]
    #                     decimal = Decimal(odd["odds"])
    #                     decimal = round(decimal, 2)
    #                     if existing_odd.odd == decimal: continue
    #                     existing_odd.odd = odd["odds"]
    #                     odds_to_update.append(existing_odd)
    #                     continue
                    
    #                 description = bet["headerDetail"] + " " + odd["name"]
    #                 description = description.replace(name1, "*1*").replace(name2, "*2*").replace("  ", " ")
    #                 odds_to_create.append(OddModel(
    #                     bet_id = int(bet_id),
    #                     odd = odd["odds"],
    #                     event_id = event_id,
    #                     market_id = market_id,
    #                     opp_description = description,
    #                     tip_type = tip, 
    #                     bet_order = bet_order,
    #                     opp_number="0"
    #                 ))        
    #         odds_to_delete.extend(existing_match_odds.values())          
    #     return odds_to_create, odds_to_update, odds_to_delete       

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
            # update odds
            pass
        except Exception as ex:
            print(f"Failed import Nike data. Exception: {str(ex)}.")
    