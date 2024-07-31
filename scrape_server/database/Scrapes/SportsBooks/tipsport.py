import asyncio
from ..dataclass_models import EventModel, OddModel
from datetime import datetime
from ..common import getCommonDriver
from ..scripts import get_existing_odds
from ...models import Odd, Event
from decimal import Decimal
from .scraper import Scraper

class TipsportScraper(Scraper): 
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass    
        
    def get_driver(self):
        self.driver = getCommonDriver(True)
        url = f"https://www.tipsport.sk/live"
        self.driver.get(url)

    def close_driver(self):
        try:
            self.driver.close()
            self.driver.quit()
        except:
            pass    

    async def gather_events(self, driver, sport_id: int):
        script = f"""
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
            "url": "https://www.tipsport.sk/kurzy/{self.request.url}"
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
        result = await self.execute_driver_script(driver, script)
        return result
    
    async def gather_odds(self):
        tasks = []
        for matchId in self.match_ids: 
            tasks.append(asyncio.create_task(self.get_detail_response(matchId)))
        results = await asyncio.gather(*tasks)
        return results

    async def get_detail_response(self, matchId: int):
        script = f"""
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
        parsed_data = await self.execute_driver_script(script)
        return (matchId, parsed_data)
    
    def map_events(self, data: dict[int, object]) -> list[EventModel]: 
        events: list[EventModel] = []
        leagues = result["offerSuperSports"][0]["tabs"][0]["offerCompetitionAnnuals"]  
        for league in leagues: 
            matches = league["matches"]
            for match in matches: 
                try:
                    if match["matchType"] != "MATCH": continue
                    try:
                        short_names = match["name"].split(" - ")
                        if len(short_names) != 2:
                            short_names = match["name"].split("-")
                            if len(short_names) != 2: continue
                        short_names = [name.strip() for name in short_names]
                        full_name1 = match["participantHome"] if "participantHome" in match else match["homeParticipant"]
                        full_name2 = match["participantVisiting"] if "participantVisiting" in match else match["visitingParticipant"]
                    except Exception as ex:
                        continue
                    dt_object = datetime.fromisoformat(match['datetimeClosed'])  
                    self.names[match["id"]] = [full_name1, full_name2, *short_names]
                    self.match_ids.append(int(match["id"]))
                    events.append(EventModel(match["id"], dt_object, full_name1, full_name2))
                except:
                    continue
        return events        
    
    def map_odds(self, data: list[object]) -> tuple[list[OddModel], list[Odd]]:
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        if all(element is None for _ , element in details):
            raise Exception('No details retrieved.')
        existing_odds = get_existing_odds(self.request.sportsbook_id, self.request.sport_id)
        for match_id, detail in details: 
            if detail is None: continue
            try:
                names = self.names[match_id]
                full_name1 = names[0]
                full_name2 = names[1]
                short_name1 = names[2]
                short_name2 = names[3]
            except Exception as ex:
                continue

            existing_match_odds = existing_odds[match_id]

            for table in detail["eventTables"]:
                if table["maxColumns"][0] == 3: 
                    if 'CORNER_WINNER' in table["mySelectionId"]: continue
                    if 'WINNER_3W_AT_TIME' in table["mySelectionId"]: continue 
                    if 'WINNER' not in table["mySelectionId"]: continue
                elif table["maxColumns"][0] != 2: continue
                if '_AND_' in table["mySelectionId"]: continue
                if 'EXACT_RESULT' in table["mySelectionId"]: continue
                if 'WINNER_OR_LEAD' in table["mySelectionId"]: continue
                if 'HOW_WILL_TIE_BE_DECIDED' in table["mySelectionId"]: continue
                if 'WINNING_MARGIN_INTERVAL' in table["mySelectionId"]: continue
                if 'METHOD_OF_QUALIFICATION' in table["mySelectionId"]: continue

                replacePlayers, replacePlayer = False, False
                if 'PLAYERS' in table["mySelectionId"]:
                    continue
                    replacePlayers= True
                elif 'PLAYER' in table["mySelectionId"]:
                    continue
                    replacePlayer = True 

                opp_name = table["name"]
                if self.request.sport_id == 9 and opp_name == "Víťaz série":
                    opp_name = "Kto postúpi"

                for box in table["boxes"]:
                    box_name = None
                    if "name" in box:
                        box_name = box["name"]
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
                        cell_name = cell["name"]
                        if box_name is not None:
                            description = opp_name + " " + box_name + " " +  cell_name
                        else:
                            description = opp_name + " " +  cell_name

                        description = self.replace_by_tokens(description, [
                            (full_name1, " *1* "),
                            (full_name2, " *2* "),
                            (short_name1, " *1* "),
                            (short_name2, " *2* "),
                        ])
                        description = description.replace(" Ž", " ").strip()
                        description = description.replace(" U19", " ").strip()
                        description = description.replace("  ", " ").replace("  ", " ")
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

        return odds_to_create, odds_to_update

    def map_events_selected(self, events: list[Event], event_response: dict[int, object]) -> tuple[list[Event], list[Event]]:
        pass

    def map_odds_selected(self, events: list[Event], odds_response: list[object])-> list[Odd]:
        pass

# NOTE: kto postupi a vitaz serie v hokeji su ta ista vec.

# url_numbers = {
#                 'tenis-43': 43, 
#                 'sipky-42': 42, 
#                 'kriket-169': 169, 
#                 'baseball-6': 6, 
#                 'stolny-tenis-40': 40, 
#                 'snooker-37': 37, 
#                 'volejbal-47': 47, 
#                 'futbal-16': 16, 
#                 'hokej-23': 23
#             }