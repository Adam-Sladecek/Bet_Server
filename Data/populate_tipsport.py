import aiohttp 
import asyncio
import json

async def getData(url, sport_id, session_id):
    async with aiohttp.ClientSession() as session:
        result = await get_response(session, url, sport_id, session_id)
    if not result: raise Exception
    mapped_result = get_bets_tipsport(result)
    return mapped_result

async def get_response(session, url, sport_id, session_id):
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

async def get_details(url, matchIds, session_id):
    async with aiohttp.ClientSession() as session:
        results = []
        tasks = []
        for matchId in matchIds: 
            tasks.append(asyncio.create_task(get_detail_response(session, url, matchId, session_id)))
        results = await asyncio.gather(*tasks)
        return results

async def get_detail_response(session, url, matchId, session_id):
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

def get_bets_tipsport(result):  
    try:
        match_ids = []
        names = dict()
        leagues = result["offerSuperSports"][0]["tabs"][0]["offerCompetitionAnnuals"]  
        for league in leagues: 
            matches = league["matches"]
            for match in matches: 
                try:
                    if match["matchType"] != "MATCH": continue
                    match_ids.append(match["id"])
                    short_names = match["name"].split(" - ")
                    if len(short_names) != 2:
                        short_names = match["name"].split("-")
                        if len(short_names) != 2:
                            continue
                    names[match["id"]] = [match["nameFull"], *short_names]
                except:
                    continue
        return match_ids, names
    except Exception as ex: 
        return None, None

def get_opportunities(all_details, all_names):
    # try:
    all_opportunities = []
    used_touples = set()
    for key, details in all_details.items(): 
        if details is None: continue
        names = all_names[key]
        for match_id, detail in details: 
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
                        cell_name = cell["name"].replace(player1name, " *1* ").replace(player2name, " *2* ")
                        if box_name is not None:
                            description = opp_name + " " + box_name + " " +  cell_name
                        else:
                            description = opp_name + " " +  cell_name
                        description = description.replace("  ", " ").strip()
                        if (description, key) in used_touples: continue
                        used_touples.add((description, key))
                        all_opportunities.append({"id": len(all_opportunities) + 1, "tip_type": "X", "opp_number": cell["oppNumber"], "opp_description": description, "sport_id": key, "sportsbook_id": 4})
    return all_opportunities                            
    # except Exception as ex: 
    #     return []                    

def getCommonDriver(showBrowser):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    service = Service('chromedriver.exe')
    options = Options()
    if not showBrowser: 
        options.add_argument("--headless")
    options.add_argument('log-level=3')   
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(service= service, options = options)
    
async def populate_tipsport(): 
    urls = [(1, 'tenis-43', 43), (2, 'sipky-42', 42), (3, 'kriket-169', 169), (4, 'baseball-6', 6), (5, 'stolny-tenis-40', 40), (6, 'snooker-37', 37), (7, 'volejbal-47', 47), (8, 'futbal-16', 16), (9, 'hokej-23', 23)]
    # try:
    driver = getCommonDriver(False)
    url = "https://www.tipsport.sk/"
    driver.get(url)
    cookies = driver.get_cookies()
    session_id = next((cookie['value'] for cookie in cookies if cookie['name'] == 'JSESSIONID'), None)
    driver.close()
    driver.quit()
    all_details = dict()
    all_names = dict()
    for index, url, sport_id in urls: 
        matchIds, names = await getData(url, sport_id, session_id)
        if matchIds is None: 
            all_details[index] = None
            continue
        details = await get_details(url, matchIds, session_id)
        all_details[index] = details
        all_names[index] = names
    all_opportunities = get_opportunities(all_details, all_names)
    with open("Data/tipsport.json", "w", encoding='utf-8') as f:
        f.write('[\n')
        for opp in all_opportunities[:-1]: 
            json.dump(opp, f, ensure_ascii=False)
            f.write(',\n')
        json.dump(all_opportunities[-1], f, ensure_ascii=False)    
        f.write('\n')    
        f.write(']\n')
    # except Exception as ex:
    #     print("Failed to get Tipsport bets")
    #     return None

if __name__ == '__main__':
    loop = asyncio.run(populate_tipsport())