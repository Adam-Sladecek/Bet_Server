import aiohttp 
import asyncio
import queue

import requests
from Models import EventModel, OddModel, RequestModel, Event, Odd, ScrapeResultModel
from datetime import datetime
import threading
from Logging import configure_logging, logger
import logging
from .common import getCommonDriver
import json 

async def getData(url: str, sport_id: int, session_id: str, request: RequestModel) -> tuple[list[int], dict[int, list[tuple[str, str, str]]], list[EventModel]]:
    async with aiohttp.ClientSession() as session:
        result = await get_response(session, url, sport_id, session_id)
    if not result: raise Exception
    mapped_result = get_events(result, request)
    return mapped_result

async def get_response(session: aiohttp.ClientSession, url: str, sport_id: int, session_id: str):
    body = {
        'id': sport_id, 
        'limit': 10000,
        'type': 'SUPERSPORT', 
        'url': f"https://www.tipsport.sk/kurzy/{url}",
    }
    content_length = len(json.dumps(body))
    headers = {
        'Content-Type': 'application/json',
        'Content-Length': str(content_length),
        'Host': 'www.tipsport.sk', 
        'Origin': 'https://www.tipsport.sk', 
        'Referer': f"https://www.tipsport.sk/kurzy/{url}",
        'Cookie': f"JSESSIONID={session_id}",
    }
    async with session.post('https://www.tipsport.sk/rest/offer/v2/offer?limit=10000', data=json.dumps(body), headers=headers) as resp:
        result = await resp.json()
        return result

async def get_details(url: str, matchIds: list[int], session_id: str, request: RequestModel, names: dict[int, list[tuple[str, str, str]]]) -> dict[int, list[OddModel]]:
    async with aiohttp.ClientSession() as session:
        results = []
        tasks = []
        for matchId in matchIds: 
            tasks.append(asyncio.create_task(get_detail_response(session, url, matchId, session_id)))
        results = await asyncio.gather(*tasks)
        mapped_result = get_bets(results, request, names)
        return mapped_result

async def get_detail_response(session: aiohttp.ClientSession, url: str, matchId: int, session_id: str):
    headers = {
        'Host': 'www.tipsport.sk',
        'Referer': f"https://www.tipsport.sk/kurzy/{url}?limit=10000&matchId={matchId}",
        'Cookie': f"JSESSIONID={session_id}",
    }
    async with session.get(f'https://www.tipsport.sk/rest/offer/v1/matches/{matchId}/event-tables?fromResults=false&ticketBuilderId=1', headers=headers) as resp:
        try:   
            result = await resp.json() 
        except Exception as ex:
            return None
        return (matchId, result)
    
def get_events(result, request: RequestModel) -> tuple[list[int], dict[int, list[tuple[str, str, str]]], list[EventModel]]: 
    if result is None: 
        return None, None, None 
    match_ids: list[int] = []
    names: dict[int, list[tuple[str, str, str]]] = dict()
    events: list[EventModel] = []
    leagues = result["offerSuperSports"][0]["tabs"][0]["offerCompetitionAnnuals"]  
    for league in leagues: 
        matches = league["matches"]
        for match in matches: 
            try:
                if match["matchType"] != "MATCH": continue
                short_names = match["name"].split(" - ")
                if len(short_names) != 2:
                    short_names = match["name"].split("-")
                    if len(short_names) != 2:
                        continue
                dt_object = datetime.fromisoformat(match['datetimeClosed'])
                formatted_time = dt_object.strftime('%d/%m/%Y %H:%M:%S')
                time = datetime.strptime(formatted_time, '%d/%m/%Y %H:%M:%S')    
                names[match["id"]] = [match["nameFull"], *short_names]
                match_ids.append(int(match["id"]))
                events.append(EventModel(match["id"], request.sportsbook_id, request.sport_id, time.isoformat(), short_names[0], short_names[1]))
            except:
                continue
    return match_ids, names, events
    
def get_bets(details, request: RequestModel, names: dict[int, list[tuple[str, str, str]]]) -> dict[int, list[OddModel]]:
    odds: dict[int, list[OddModel]] = {} 
    if details is None: return None
    for match_id, detail in details: 
        odds[match_id] = []
        player1name = names[match_id][1]
        player2name = names[match_id][2]
        for table in detail["eventTables"]:
            if 'AND' in table["mySelectionId"]: 
                continue
            if table["maxColumns"][0] == 3: 
                if 'WINNER' not in table["mySelectionId"]:
                    continue
            elif table["maxColumns"][0] != 2: 
                continue
            replacePlayers, replacePlayer = False, False
            if 'PLAYERS' in table["mySelectionId"]:
                replacePlayers= True
            elif 'PLAYER' in table["mySelectionId"]:
                replacePlayer = True    
            opp_name = table["name"].replace(player1name, " *1* ").replace(player2name, " *2* ")
            for box in table["boxes"]:
                box_name = None
                if "name" in box:
                    box_name = box["name"].replace(player1name, " *1* ").replace(player2name, " *2* ")
                    if replacePlayers:
                            splits= box_name.split(", ")
                            if len(splits) != 2 : continue
                            box_name = box_name.replace(splits[0], "*name1*").replace(splits[1], "*name2*")
                    elif replacePlayer:
                        box_name = "*name*"
                for cell in box["cells"]:
                    if not cell["active"]: continue
                    cell_name = cell["name"].replace(player1name, " *1* ").replace(player2name, " *2* ")
                    if box_name is not None:
                        description = opp_name + " " + box_name + " " +  cell_name
                    else:
                        description = opp_name + " " +  cell_name
                    description = description.replace("  ", " ").strip()
                    odds[match_id].append(OddModel(
                            bet_id = cell["id"],
                            odd = cell["odd"],
                            market_id="0",
                            event_id = match_id,
                            sportsbook_id = request.sportsbook_id,
                            opp_description = description,
                            tip_type = "X", 
                            opp_number = cell["oppNumber"],
                            bet_order=0,
                            opportunity_id=0
                        ))  
    return odds   

async def tipsport_getData(request: RequestModel, result_queue: queue.Queue, logger: logging.Logger, test: bool = False):
    try:
        url_numbers = {
            'tenis-43': 43, 
            'sipky-42': 42, 
            'kriket-169': 169, 
            'baseball-6': 6, 
            'stolny-tenis-40': 40, 
            'snooker-37': 37, 
            'volejbal-47': 47, 
            'futbal-16': 16, 
            'hokej-23': 23
        }
        driver = getCommonDriver(False)
        url = "https://www.tipsport.sk/"
        driver.get(url)
        cookies = driver.get_cookies()
        session_id = next((cookie['value'] for cookie in cookies if cookie['name'] == 'JSESSIONID'), None)
        driver.close()
        driver.quit()
        matchIds, names, events = await getData(request.url, url_numbers[request.url], session_id, request)
        details_promise = get_details(request.url, matchIds, session_id, request, names)
        if not test: 
            event_update_obj = {
                "data" : {
                    'events': [event.__dict__ for event in events],
                    'sport_id': request.sport_id,
                    'sportsbook_id': request.sportsbook_id,
                },
                "url": "http://127.0.0.1:5000/events"
            }
            result_queue.put(event_update_obj)
            details = await details_promise
            odd_update_obj = {
                "data" : {
                'odd_model_dict': {key: [odd.__dict__ for odd in value] for key, value in details.items()},
                'sport_id': request.sport_id,
                'sportsbook_id': request.sportsbook_id,
                },
                "url": "http://127.0.0.1:5000/odds"
            }
            result_queue.put(odd_update_obj)
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
        print("Failed to get Tipsport driver")

def populate_tipsport(*args, **kwargs):
    asyncio.run(tipsport_getData(*args, **kwargs))

if __name__ == "__main__":
    request = RequestModel(sport_name = "Tennis", sportsbook_name = "Tipsport", sport_id = 1, sport_type_id = 1, url = "tenis-43", is_tipos_more=False)
    populate_tipsport(request, None, None, test=True)