import aiohttp 
import asyncio
import json

async def getData(order, url):
    responses = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        tasks.append(asyncio.create_task(get_response(session, f'https://nike.sk/api-gw/nikeone/v1/boxes/search/portal?betNumbers&date&limit=50&live=false&menu=%2F{url}&minutes&order{order}&prematch=true&results=false')))
        results = await asyncio.gather(*tasks)
        for result in results:
            responses.append(result)
    return responses
      
async def get_response(session, url):
    async with session.get(url) as resp:
        result = await resp.json()    
        return result

async def get_details(result_dict):
    opps = []
    used_touples = set()
    counter = 1
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
                except:
                    continue    
                for bet in result["bets"]:
                    if (bet["marketId"], bet["betOrder"], key) in used_touples: continue
                    used_touples.add((bet["marketId"], bet["betOrder"], key))
                    if key in [8,9] and bet["headerDetail"] == "Zápas": 
                        array = bet["selectionGrid"][0] + bet["selectionGrid"][1]
                        for odd in array: 
                            description = bet["headerDetail"] + " " + odd["name"]
                            if "tip" not in odd: continue
                            tip = odd["tip"] # TODO: replace like in doxxet, add sportsbookid
                            opps.append({"id" : counter, "market_id" : bet["marketId"], "opp_description": description.replace(name1, "*1*").replace(name2, "*2*").replace("  ", " "), "tip_type": tip, "bet_order": int(bet["betOrder"]), "sport_id": key, "sportsbook_id": 3})
                            counter += 1
                            continue
                    if bet["rows"] != 1: continue
                    if len(bet["selectionGrid"][0]) != 2: continue
                    for odd in bet["selectionGrid"][0]: 
                        description = bet["headerDetail"] + " " + odd["name"]
                        if "tip" not in odd: continue
                        tip = odd["tip"]
                        opps.append({"id" : counter, "market_id" : bet["marketId"], "opp_description": description.replace(name1, "*1*").replace(name2, "*2*").replace("  ", " "), "tip_type": tip, "bet_order": int(bet["betOrder"]), "sport_id": key, "sportsbook_id": 3})
                        counter += 1
    return opps       

def getInfoForDetails(result, resultjson):
    for bet in resultjson[0]['bets']:
        for box in resultjson[0]['boxes']:
            if bet['sportEventId'] in box["sportEventIds"]:
                box_id = box["boxId"]
        result.append((box_id, bet['sportEventId']))
    return result    

async def nike_getData():
    try:
        order = ''
        counter = 0
        result_dict = dict()
        urls = [('tenis', 1), ('sipky', 2), ('kriket', 3), ('baseball', 4), ('stolny-tenis', 5), ('snooker', 6), ('volejbal', 7), ('futbal', 8), ('hokej', 9)]
        for url, sport_id in urls: 
            result = []
            while True:
                if counter >= 100:
                    print('Nike too many requests.')
                    break
                resultjson = await getData(order, url)
                result = getInfoForDetails(result, resultjson)
                if not resultjson[0]['hasMoreBets']:
                    order = None
                    break
                order = '=' + str(int(resultjson[0]['maxBoxOrder']))
                counter += 1
            result_dict[sport_id] = result   
        opps = await get_details(result_dict)
        with open("Data/nike.json", "w", encoding='utf-8') as f:
            f.write('[\n')
            for opp in opps[:-1]: 
                json.dump(opp, f, ensure_ascii=False)
                f.write(',\n')
            json.dump(opps[-1], f, ensure_ascii=False)    
            f.write('\n')    
            f.write(']\n')
    except Exception as ex:
        print("Failed to get Nike driver")
        return None

def populate_nike():
    asyncio.run(nike_getData())

if __name__ == "__main__":
    populate_nike()