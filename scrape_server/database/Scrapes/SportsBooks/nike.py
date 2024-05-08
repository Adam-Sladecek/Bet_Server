import asyncio
from datetime import datetime
from decimal import Decimal
from .scraper import Scraper
from ..dataclass_models import EventModel, OddModel, RequestModel
from ..scripts import get_existing_odds, update_events
from ...models import Odd

class NikeScraper(Scraper):
    def __init__(self, request: RequestModel):
        self.request = request
        self.detail_ids: list[tuple[int,int]] = []
        self.events: list[EventModel] = []

    async def gather_events(self, order: str):
        urls = [f'https://nike.sk/api-gw/nikeone/v1/boxes/search/portal?betNumbers&date&limit=50&live=false&menu=%2F{self.request.url}&minutes&order{order}&prematch=true&results=false']
        return await self.gather_data(urls)

    async def gather_details(self):
        urls = []
        for box_id, sport_event_id in self.detail_ids:
            if box_id is None or sport_event_id is None: continue
            urls.append(f'https://www.nike.sk/api-gw/nikeone/v1/boxes/extended/sport-event-id?boxId={box_id}&sportEventId={sport_event_id}')
        return await self.gather_data(urls)
    
    def map_events(self, result):
        if result is None: return
        for bet in result[0]['bets']:
            try:
                for box in result[0]['boxes']:
                    box_id = None
                    if box["boxId"] in ["superoffer", "superchance"]: continue
                    if bet['sportEventId'] in box["sportEventIds"]:
                        box_id = box["boxId"]
                        break
                if not box_id: continue    
                time = datetime.fromisoformat(bet['expirationTime'])
                names = bet['participants']
                self.events.append(EventModel(int(bet['sportEventId']), time, names[0], names[1]))
                self.detail_ids.append((box_id, bet['sportEventId']))
            except Exception as ex: 
                continue    
    
    def map_odds(self, details) -> tuple[list[OddModel], list[Odd], list[Odd]]:
        if all(element is None for element in details):
            raise Exception('No details retrieved.')
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        odds_to_delete: list[Odd] = []
        existing_odds = get_existing_odds(self.request.sportsbook_id, self.request.sport_id, True)
        for detail in details:
            try:
                name1, name2 = detail["bets"][0]["participants"]
                event_id = int(detail["sportEvents"][0]["sportEventId"])
                existing_match_odds = existing_odds[event_id]
            except:
                continue    
            for bet in detail["bets"]:
                market_id = bet["marketId"]
                bet_id = bet["betId"]
                bet_order = int(bet["betOrder"])
                if self.request.sport_id in [8,9] and bet["headerDetail"] == "Zápas": 
                    array = bet["selectionGrid"][0] + bet["selectionGrid"][1]
                else: 
                    if bet["rows"] != 1 or len(bet["selectionGrid"][0]) != 2: continue
                    array = bet["selectionGrid"][0]    
                for odd in array: 
                    try:
                        if not odd["enabled"] or odd["locked"] or "tip" not in odd: continue
                    except Exception as ex:
                        continue

                    tip = odd["tip"]
                    if (int(bet_id), tip) in existing_match_odds: 
                        existing_odd = existing_match_odds[(int(bet_id), tip)]
                        del existing_match_odds[(int(bet_id), tip)]
                        decimal = Decimal(odd["odds"])
                        decimal = round(decimal, 2)
                        if existing_odd.odd == decimal: continue
                        existing_odd.odd = odd["odds"]
                        odds_to_update.append(existing_odd)
                        continue
                    
                    description = bet["headerDetail"] + " " + odd["name"]
                    description = description.replace(name1, "*1*").replace(name2, "*2*").replace("  ", " ")
                    odds_to_create.append(OddModel(
                        bet_id = int(bet_id),
                        odd = odd["odds"],
                        event_id = event_id,
                        market_id = market_id,
                        opp_description = description,
                        tip_type = tip, 
                        bet_order = bet_order,
                        opp_number="0"
                    ))        
            odds_to_delete.extend(existing_match_odds.values())          
        return odds_to_create, odds_to_update, odds_to_delete       

    def get_data(self):
        try:
            order = ''
            counter = 0
            while True:
                if counter >= 100:
                    print('Nike too many requests.')
                    break
                resultjson = asyncio.run(self.gather_events(order)) 
                self.map_events(resultjson)
                if not resultjson[0]['hasMoreBets']:
                    break
                order = '=' + str(int(resultjson[0]['maxBoxOrder']))
                counter += 1
            update_events(self.events, self.request.sport_id, self.request.sportsbook_id)    
            details_results = asyncio.run(self.gather_details())
            return self.map_odds(details_results)
        except Exception as ex:
            print(f"Failed to get Nike driver {str(ex)}.")
            return None, None, None

# if __name__ == "__main__":
#     request = RequestModel(sport_name = "Tennis", sportsbook_name = "Nike", sport_id = 1, sport_type_id = 1, url = "tenis", is_tipos_more=False)
#     scraper = NikeScraper(request)
#     odds_to_create, odds_to_update, odds_to_delete = scraper.get_data()
#     print(f'# OTC : {len(odds_to_create)}, # OTC : {len(odds_to_update)},# OTC : {len(odds_to_delete)}')
    