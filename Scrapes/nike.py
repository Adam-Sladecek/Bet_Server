import aiohttp 
import asyncio
import queue
from Models import EventModel, OddModel, RequestModel, Event, Odd, ScrapeResultModel
from datetime import datetime
import threading
import logging

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

async def get_details(result_dict: dict[int, tuple[int,int]], request: RequestModel) -> dict[int, list[OddModel]]:
    odds: dict[int, list[OddModel]] = {} 
    async with aiohttp.ClientSession() as session:
        for key, value in result_dict.items():
            tasks = []
            for box_id, sport_event_id in value:
                if box_id is None or sport_event_id is None: continue
                tasks.append(asyncio.create_task(get_response(session, f'https://www.nike.sk/api-gw/nikeone/v1/boxes/extended/sport-event-id?boxId={box_id}&sportEventId={sport_event_id}')))
            results = await asyncio.gather(*tasks)
            for result in results:
                try:
                    name1, name2 = result["bets"][0]["participants"]
                    event_id = result["sportEvents"][0]["sportEventId"]
                    odds[event_id] = []
                except:
                    continue    
                for bet in result["bets"]:
                    market_id = bet["marketId"]
                    bet_id = bet["betId"]
                    bet_order = int(bet["betOrder"])
                    if key in [8,9] and bet["headerDetail"] == "Zápas": 
                        array = bet["selectionGrid"][0] + bet["selectionGrid"][1]
                    else: 
                        if bet["rows"] != 1 or len(bet["selectionGrid"][0]) != 2: continue
                        array = bet["selectionGrid"][0]    
                    for odd in array: 
                        if not odd["enabled"] or odd["locked"] or "tip" not in odd: continue
                        description = bet["headerDetail"] + " " + odd["name"]
                        tip = odd["tip"]
                        description = description.replace(name1, "*1*").replace(name2, "*2*").replace("  ", " ")
                        odds[event_id].append(OddModel(
                            bet_id = bet_id,
                            odd = odd["odds"],
                            event_id = event_id,
                            sportsbook_id = request.sportsbook_id,
                            market_id = market_id,
                            opp_description = description,
                            tip_type = tip, 
                            bet_order = bet_order
                        ))          
    return odds       

def getInfoForDetails(detail_ids: list[tuple[int,int]], resultjson, events: list[EventModel], request: RequestModel) -> tuple[list[tuple[int,int]], list[EventModel]]:
    for bet in resultjson[0]['bets']:
        try:
            for box in resultjson[0]['boxes']:
                if bet['sportEventId'] in box["sportEventIds"]:
                    box_id = box["boxId"]
                    break
            dt_object = datetime.fromisoformat(bet['expirationTime'])
            formatted_time = dt_object.strftime('%d/%m/%Y %H:%M:%S')
            time = datetime.strptime(formatted_time, '%d/%m/%Y %H:%M:%S')
            names = bet['participants']
            events.append(EventModel(bet['sportEventId'], request.sportsbook_id, request.sport_id, time, names[0], names[1]))
            detail_ids.append((box_id, bet['sportEventId']))
        except: 
            continue    
    return detail_ids, events

async def nike_getData(request: RequestModel, result_queue: queue.Queue, logger: logging.Logger, test: bool = False):
    try:
        order = ''
        counter = 0
        detail_ids: list[tuple[int,int]] = []
        events: list[EventModel] = []
        while True:
            if counter >= 100:
                print('Nike too many requests.')
                break
            resultjson = await getData(order, request.url)
            detail_ids, events = getInfoForDetails(detail_ids, resultjson, events, request)
            if not resultjson[0]['hasMoreBets']:
                order = None
                break
            order = '=' + str(int(resultjson[0]['maxBoxOrder']))
            counter += 1
        details_promise = get_details({request.sport_id: detail_ids}, request)
        if not test: 
            calc_thread = threading.Thread(target = Event.update_events, args = (events, request.sport_id, request.sportsbook_id))
            calc_thread.start()
            details = await details_promise
            calc_thread.join()
            odd_thread = threading.Thread(target = Odd.update_odds, args = (details, request.sport_id, request.sportsbook_id))
            odd_thread.start()
            odd_thread.join()
            scrape_result = ScrapeResultModel(
                success = True,
                request = request
            )
            result_queue.put(scrape_result)
            return
        print(await details_promise)
        
    except Exception as ex:
        scrape_result = ScrapeResultModel(
            success = False,
            request = request
        )
        result_queue.put(scrape_result)
        logger.error(str(ex))
        print("Failed to get Nike driver")

def populate_nike(*args, **kwargs):
    asyncio.run(nike_getData(*args, **kwargs))

if __name__ == "__main__":
    request = RequestModel(sport_name = "Tennis", sportsbook_name = "Nike", sport_id = 1, sport_type_id = 1, url = "tenis", is_tipos_more=False)
    populate_nike(request, None, None, test=True)