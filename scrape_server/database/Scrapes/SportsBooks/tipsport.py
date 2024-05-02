import asyncio
from ..dataclass_models import EventModel, OddModel, RequestModel
from datetime import datetime
from ..common import getCommonDriver
import json
from ..scripts import get_existing_odds, update_events
from ...models import Odd
from decimal import Decimal

def getData(driver, url: str, sport_id: int, request: RequestModel) -> tuple[list[int], dict[int, list[tuple[str, str, str]]], list[EventModel]]:
    result = get_response(driver, url, sport_id)
    mapped_result = get_events(result, request)
    return mapped_result

def get_response(driver, url: str, sport_id: int):
    post_script = f"""
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "https://www.tipsport.sk/rest/offer/v2/offer?limit=3000", false);
    xhr.setRequestHeader("Content-Type", "application/json");
    var payload = JSON.stringify({{
        "fulltexts": [],
        "highlightAnyTime": false,
        "id": {sport_id},
        "limit": 3000,
        "matchIds": [],
        "matchViewFilters": [],
        "results": false,
        "type": "SUPERSPORT",
        "url": "https://www.tipsport.sk/kurzy/{url}"
    }});
    xhr.onreadystatechange = function () {{
        if (xhr.readyState == 4) {{
            if (xhr.status == 200) {{
                window.responseData = xhr.responseText;
            }} else {{
                console.error("Request failed with status:", xhr.status);
                window.responseData = null;
            }}
        }}
    }};
    xhr.send(payload);
    """
    try:
        driver.execute_script(post_script)
        response_data = driver.execute_script("return window.responseData;")
        parsed_data = json.loads(response_data)
    except:
        parsed_data = None
    return parsed_data

async def get_details(driver, matchIds: list[int]) -> list:
    results = []
    tasks = []
    for matchId in matchIds: 
        tasks.append(asyncio.create_task(get_detail_response(driver, matchId)))
    results = await asyncio.gather(*tasks)
    return results

async def get_detail_response(driver, matchId: int):
    post_script = f"""
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "https://www.tipsport.sk/rest/offer/v1/matches/{matchId}/event-tables?fromResults=false&ticketBuilderId=1", false);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {{
        if (xhr.readyState == 4) {{
            if (xhr.status == 200) {{
                window.responseData = xhr.responseText;
            }} else {{
                console.error("Request failed with status:", xhr.status);
                window.responseData = null;
            }}
        }}
    }};
    xhr.send();
    """
    try:
        driver.execute_script(post_script)
        response_data = driver.execute_script("return window.responseData;")
        parsed_data = json.loads(response_data)
        return (matchId, parsed_data)
    except:
        return None
    
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
                    if len(short_names) != 2: continue
                dt_object = datetime.fromisoformat(match['datetimeClosed'])  
                names[match["id"]] = [match["nameFull"], *short_names]
                match_ids.append(int(match["id"]))
                events.append(EventModel(match["id"], dt_object, short_names[0], short_names[1]))
            except:
                continue
    return match_ids, names, events
    
def get_bets(details, request: RequestModel, names: dict[int, list[tuple[str, str, str]]]) -> tuple[list[OddModel], list[Odd], list[Odd]]:
    odds_to_create: list[OddModel] = []
    odds_to_update: list[Odd] = []
    odds_to_delete: list[Odd] = []
    if details is None: return [], [], []
    existing_odds = get_existing_odds(request.sportsbook_id, request.sport_id)
    for match_id, detail in details: 
        player1name = names[match_id][1]
        player2name = names[match_id][2]

        existing_match_odds = existing_odds[match_id]

        for table in detail["eventTables"]:
            if 'AND' in table["mySelectionId"]: continue
            if table["maxColumns"][0] == 3: 
                if 'WINNER' not in table["mySelectionId"]: continue
            elif table["maxColumns"][0] != 2: continue

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

                    if cell["id"] in existing_match_odds: 
                        existing_odd = existing_match_odds[cell["id"]]
                        del existing_match_odds[cell["id"]]
                        decimal = Decimal(cell["odd"])
                        decimal = round(decimal, 2)
                        if existing_odd.odd == decimal: continue
                        existing_odd.odd = cell["odd"]
                        odds_to_update.append(existing_odd)
                        continue

                    cell_name = cell["name"].replace(player1name, " *1* ").replace(player2name, " *2* ")
                    if box_name is not None:
                        description = opp_name + " " + box_name + " " +  cell_name
                    else:
                        description = opp_name + " " +  cell_name
                    description = description.replace("  ", " ").strip()
                    try:
                        odds_to_create.append(OddModel(
                                bet_id = cell["id"],
                                odd = float(cell["odd"]),
                                market_id="0",
                                event_id = match_id,
                                opp_description = description,
                                tip_type = "X", 
                                opp_number = cell["oppNumber"],
                                bet_order=0
                            ))  
                    except Exception as ex: 
                        continue    
        odds_to_delete.extend(existing_match_odds.values())

    return odds_to_create, odds_to_update, odds_to_delete

def tipsport_getData(request: RequestModel, test: bool = False):
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
        driver = getCommonDriver(True)
        url = f"https://www.tipsport.sk/kurzy/{request.url}"
        driver.get(url)
        matchIds, names, events = getData(driver, request.url, url_numbers[request.url], request)
        update_events(events, request.sport_id, request.sportsbook_id)
        details_results = asyncio.run(get_details(driver, matchIds))
        odds_to_create, odds_to_update, odds_to_delete = get_bets(details_results, request, names)
        driver.close()
        driver.quit()
        if not test: 
            return odds_to_create, odds_to_update, odds_to_delete
        else:
            print("Done")

    except Exception as ex:
        print(f"Failed to get Tipsport driver {str(ex)}.")
        return None, None

if __name__ == "__main__":
    request = RequestModel(sport_name = "Tennis", sportsbook_name = "Tipsport", sport_id = 1, sport_type_id = 1, sportsbook_id= 6, url = "tenis-43", is_tipos_more=False)
    tipsport_getData(request, test=True)

# TODO: scrape using driver in all api sportsbooks