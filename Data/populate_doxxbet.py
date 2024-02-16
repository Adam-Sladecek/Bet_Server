import aiohttp 
import asyncio
import json
import time

async def getData(url, sportNumber):
    async with aiohttp.ClientSession() as session:
        result = await get_response(session, sportNumber, url)
    if not result: raise Exception
    mapped_result = getBetsDoxxbet(result)
    return mapped_result
      
async def get_response(session, sportNumber, url):
    headers = {"Host": "www.doxxbet.sk", "Origin": "https://www.doxxbet.sk", "Referer": f"https://www.doxxbet.sk/sk/sportove-tipovanie/{url}"}
    body = {'sportEvent': -1, 'leaugeCup':-1, 'live': -1, 'region': -1, 'sport': sportNumber, 'sportEvent': -1, 'streamOnly': -1, 'top': -1}
    async with session.post('https://www.doxxbet.sk/offer/GetOfferList', data= body, headers= headers) as resp:
        result = await resp.text()
        json_data = json.loads(result)
        return json_data

async def get_details(url, eventIds, session_id):
    async with aiohttp.ClientSession() as session:
        results = []
        # tasks = []
        # for eventId in eventIds: 
        #     tasks.append(asyncio.create_task(get_detail_response(session, url, eventId)))
        # results = await asyncio.gather(*tasks)
        for eventId in eventIds:
            result = await get_detail_response(session, url, eventId, session_id)
            results.append(result)
            time.sleep(0.11)
        return results

async def get_detail_response(session, url, eventId, session_id):
    body = {'eventId' : eventId}
    json_payload = json.dumps(body)
    content_length = len(json_payload)
    headers = {"Host": "www.doxxbet.sk", "Origin": "https://www.doxxbet.sk", "Referer": f"https://www.doxxbet.sk/sk/sportove-tipovanie/{url}", "Content-Type": "application/json", "Content-Length": str(content_length), "Cookie": f"ASP.NET_SessionId={session_id}"}

    async with session.post('https://www.doxxbet.sk/offer/GetOfferEventDetail', data= json_payload, headers= headers) as resp:
        result = await resp.text() 
        try:   
            json_data = json.loads(result)
        except Exception as ex:
            return None
        return json_data

def getBetsDoxxbet(result):
    eventIds = []
    for event in result['EventChanceTypes']:
        try:
            eventIds.append(event['EventID'])
        except Exception as ex:
            continue
    return eventIds

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

async def doxxbet_getData(url_dict):
    try:
        driver = getCommonDriver(False)
        url = "https://www.doxxbet.sk/sk"
        driver.get(url)
        all_details = dict()
        cookies = driver.get_cookies()
        session_id = next((cookie['value'] for cookie in cookies if cookie['name'] == 'ASP.NET_SessionId'), None)
        driver.close()
        driver.quit()
        for key, urls in url_dict.items():
            sport_dictionary = {
                'Tennis': 58,
                'Darts': 60,
                'Kriket': 70,
                'Baseball': 49,
                'TableTennis': 82,
                'Snooker': 64,
                'Volleyball': 55,
                'Football': 54, 
                'Hockey': 53,
            }
            eventIds = await getData(urls['doxxbet'], sport_dictionary[urls['name']])
            details = await get_details(urls['doxxbet'], eventIds, session_id)  
            all_details[key] = details
        opp_descriptions = set()   
        resultarray = []
        counter = 1
        for key, values in all_details.items():
            for value in values: 
                try:
                    name1, name2 = value['Event']["EventName"].split(' vs. ')
                except Exception as ex:
                    continue    
                if value is None: continue
                odds = value["Odds"]
                for odd in odds: 
                    try:
                        even_chance_type_id = odd["EventChanceTypeID"]
                        eventchancetype = value["EventChanceTypes"][str(even_chance_type_id)]
                        if key in [8,9] and eventchancetype["ChanceTypeName"] == "Výsledok":
                            tip_type = odd["TipType"]
                            tip_id = odd["TipID"]
                            tipname = value["Labels"]["TP_" + tip_id]["Name"]
                            if tipname == "1":
                                tipname = tipname.replace("1", "*1*")
                            elif tipname == "2":
                                tipname = tipname.replace("2", "*2*") 
                            resultstring = eventchancetype["ChanceTypeName"] + " " + tipname
                            if (resultstring, key) not in opp_descriptions:
                                opp_descriptions.add((resultstring, key))
                                resultarray.append({"id": counter, "tip_type": tip_type, "opp_description": resultstring, "sport_id": key, "sportsbook_id": 6})
                                counter += 1
                            continue    
                        if eventchancetype["BetType"] != 'DUO': continue
                        has_param_limit_mark = "ParamLimitMark" in odd
                        tip_id = odd["TipID"]
                        tip_type = odd["TipType"]
                        tipname = value["Labels"]["TP_" + tip_id]["Name"].replace("1", "*1*").replace("2", "*2*")
                        has_param_limit = "ParamGroupID" in eventchancetype
                        resultstring = ""
                        if has_param_limit_mark:
                            paramgroupid = eventchancetype["ParamGroupID"]
                            chance_type_param_group = next((e for e in value["ChanceTypeParamGroups"] if e["ParamGroupID"] == paramgroupid), None)
                            resultstring += chance_type_param_group["ParamGroupName"] + " " + tipname + " " + odd["ParamLimitMark"]
                        elif has_param_limit:
                            paramgroupid = eventchancetype["ParamGroupID"]
                            chance_type_param_group = next((e for e in value["ChanceTypeParamGroups"] if e["ParamGroupID"] == paramgroupid), None)
                            resultstring += chance_type_param_group["ParamGroupName"] + " " + tipname + " " + eventchancetype["ParamLimit"]
                        else: 
                            resultstring += eventchancetype["ChanceTypeName"] + " " + tipname
                        resultstring = resultstring.replace(name1, "*1*").replace(name2, "*2*")
                        if (resultstring, key) not in opp_descriptions:
                            opp_descriptions.add((resultstring, key))
                            resultarray.append({"id": counter, "tip_type": tip_type, "opp_description": resultstring, "sport_id": key, "sportsbook_id": 6})
                            counter += 1
                    except:
                        continue
        with open("Data/doxxbet.json", "w", encoding='utf-8') as f:
            f.write('[\n')
            for opp in resultarray[:-1]: 
                json.dump(opp, f, ensure_ascii=False)
                f.write(',\n')
            json.dump(resultarray[-1], f, ensure_ascii=False)    
            f.write('\n')      
            f.write(']\n')            
    except Exception as ex:
        print("Failed to get Doxxbet bets") #  TODO: skontroluj ci pridu vsetky detaily
        return None

def populate_doxxbet():
    url_dictionary = {
        1: {
            'name': 'Tennis',
            'doxxbet': 'tenis',
        },   
        2: {
            'name': 'Darts',
            'doxxbet': 'sipky',
        },   
        3: {
            'name': 'Kriket',
            'doxxbet': 'kriket',
        },   
        4: {
            'name': 'Baseball',
            'doxxbet': 'bejzbal',
        },   
        5: {
            'name': 'TableTennis',
            'doxxbet': 'stolny-tenis',
        },   
        6: {
            'name': 'Snooker',
            'doxxbet': 'snooker',
        },   
        7: {
            'name': 'Volleyball',
            'doxxbet': 'volejbal',
        },   
        8: {
            'name': 'Football',
            'doxxbet': 'futbal',
        },   
        9: {
            'name': 'Hockey',
            'doxxbet': 'ladovy-hokej',
        },   
    }
    loop = asyncio.run(doxxbet_getData(url_dictionary))
   
if __name__ == "__main__":
    populate_doxxbet()