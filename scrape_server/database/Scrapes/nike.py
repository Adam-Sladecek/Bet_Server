import aiohttp 
import asyncio
from .dataclass_models import EventModel, OddModel, RequestModel
from datetime import datetime
from .scripts import get_existing_odds, update_events
from ..models import Odd
from decimal import Decimal

async def getData(order: str, url: str):
    responses = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        tasks.append(asyncio.create_task(get_response(session, f'https://nike.sk/api-gw/nikeone/v1/boxes/search/portal?betNumbers&date&limit=50&live=false&menu=%2F{url}&minutes&order{order}&prematch=true&results=false')))
        results = await asyncio.gather(*tasks)
        for result in results:
            responses.append(result)
    return responses
      
async def get_response(session: aiohttp.ClientSession, url:str):
    async with session.get(url) as resp:
        result = await resp.json()    
        return result

async def fetch_details(detail_ids: list[tuple[int,int]]): 
    async with aiohttp.ClientSession() as session:
        tasks = []
        for box_id, sport_event_id in detail_ids:
            if box_id is None or sport_event_id is None: continue
            tasks.append(asyncio.create_task(get_response(session, f'https://www.nike.sk/api-gw/nikeone/v1/boxes/extended/sport-event-id?boxId={box_id}&sportEventId={sport_event_id}')))
        results = await asyncio.gather(*tasks)
        return results
    
def get_bets(results, request: RequestModel) -> tuple[list[OddModel], list[Odd], list[Odd]]:
    odds_to_create: list[OddModel] = []
    odds_to_update: list[Odd] = []
    odds_to_delete: list[Odd] = []
    existing_odds = get_existing_odds(request.sportsbook_id, request.sport_id, True)
    for result in results:
        try:
            name1, name2 = result["bets"][0]["participants"]
            event_id = int(result["sportEvents"][0]["sportEventId"])
            existing_match_odds = existing_odds[event_id]
        except:
            continue    
        for bet in result["bets"]:
            market_id = bet["marketId"]
            bet_id = bet["betId"]
            bet_order = int(bet["betOrder"])
            if request.sport_id in [8,9] and bet["headerDetail"] == "Zápas": 
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
                    sportsbook_id = request.sportsbook_id,
                    market_id = market_id,
                    opp_description = description,
                    tip_type = tip, 
                    bet_order = bet_order,
                    opp_number="0",
                    opportunity_id=0
                ))        
        odds_to_delete.extend(existing_match_odds.values())          
    return odds_to_create, odds_to_update, odds_to_delete       

def get_events(detail_ids: list[tuple[int,int]], resultjson, events: list[EventModel], request: RequestModel) -> tuple[list[tuple[int,int]], list[EventModel]]:
    for bet in resultjson[0]['bets']:
        try:
            for box in resultjson[0]['boxes']:
                box_id = None
                if box["boxId"] in ["superoffer", "superchance"]: continue
                if bet['sportEventId'] in box["sportEventIds"]:
                    box_id = box["boxId"]
                    break
            if not box_id: continue    
            time = datetime.fromisoformat(bet['expirationTime'])
            # formatted_time = dt_object.strftime('%d/%m/%Y %H:%M:%S')
            # time = datetime.strptime(formatted_time, '%d/%m/%Y %H:%M:%S')
            names = bet['participants']
            events.append(EventModel(int(bet['sportEventId']), request.sportsbook_id, request.sport_id, time, names[0], names[1]))
            detail_ids.append((box_id, bet['sportEventId']))
        except Exception as ex: 
            continue    
    return detail_ids, events

def nike_getData(request: RequestModel, test: bool = False):
    try:
        order = ''
        counter = 0
        detail_ids: list[tuple[int,int]] = []
        events: list[EventModel] = []
        while True:
            if counter >= 100:
                print('Nike too many requests.')
                break
            resultjson = asyncio.run(getData(order, request.url)) 
            detail_ids, events = get_events(detail_ids, resultjson, events, request)
            if not resultjson[0]['hasMoreBets']:
                order = None
                break
            order = '=' + str(int(resultjson[0]['maxBoxOrder']))
            counter += 1
        update_events(events, request.sport_id, request.sportsbook_id)    
        details_results = asyncio.run(fetch_details(detail_ids))
        odds_to_create, odds_to_update, odds_to_delete = get_bets(details_results, request)
        if not test: 
            return odds_to_create, odds_to_update, odds_to_delete
        else:    
            print("Done")
    except Exception as ex:
        print(f"Failed to get Nike driver {str(ex)}.")
        return None, None

def populate_nike(*args, **kwargs):
    asyncio.run(nike_getData(*args, **kwargs))

if __name__ == "__main__":
    request = RequestModel(sport_name = "Tennis", sportsbook_name = "Nike", sport_id = 1, sport_type_id = 1, url = "tenis", is_tipos_more=False)
    populate_nike(request, None, None, test=True)