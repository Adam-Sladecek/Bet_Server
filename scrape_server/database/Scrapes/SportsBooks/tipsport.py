import asyncio
from ..dataclass_models import EventModel, OddModel
from ..driver import Driver
from ...models import Odd, Event, Sport, SportsbookMarket
from .scraper import Scraper

class TipsportScraper(Scraper): 
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_driver()
    
    def get_driver(self):
        self.driver = Driver(False, "https://www.tipsport.sk/live")

    def close_driver(self):
        try:
            self.driver.close()
        except Exception as ex:
            print(f'Failed to quit tipsport driver. Exception: {str(ex)}')

    async def gather_events(self, sports: list[Sport]):
        url= "https://www.tipsport.sk/rest/offer/v1/live/in-play/entities"
        return await self.driver.execute_script(url)
    
    async def gather_odds(self, events):
        tasks = [
            asyncio.create_task(
                self.driver.execute_script(
                    f"https://www.tipsport.sk/rest/offer/v3/live/matches/{event.event_id}/patches?withEventTables=true"
                )
            ) for event in events
        ]
        return await asyncio.gather(*tasks)
    
    def map_events(self, data: object) -> list[EventModel]: 
        events: list[EventModel] = []
        matches = data.get("patches", [{}])[0].get("value", {}).get("matches", [])
        sport_ids = self.get_sportids()
        for match in matches: 
            try:
                names = match.get("nameFull", "").split(" - ")
                if len(names) != 2: 
                    continue
                
                sport_id = sport_ids.get(match.get("superSportId"))
                if sport_id is None: 
                    continue
                
                home, away = [name.strip() for name in names]
                time = match.get("score", {}).get("statusOffer", "")
                events.append(EventModel(
                    id=None, 
                    event_id=match["id"], 
                    league_id=0, 
                    time =time, 
                    home=home, 
                    away=away, 
                    is_default=self.sportsbook.is_default, 
                    selected=False, 
                    sportsbook_id=self.sportsbook.pk, 
                    sport_id=sport_id,
                    available_sportsbooks=[], 
                    odd_count=0,
                ))
            except Exception as ex: 
                print(f"Exception in map_events Tipsport: {str(ex)}.")
                continue  
        return events   

    def get_sportids(self) -> dict[int, int]: 
        sport_ids = {
            16: 1, #futbal
            23: 2, #hokej
            43: 3, #tenis
            7: 4,  #basketbal
            -17: 5, #doplnit handball
            47: 6, #volejbal
            40: 7, #stolny tenis
            -18: 8, #doplnit box
        }
        
        return sport_ids
    
    def map_odds(self, data: list[object]) -> tuple[list[OddModel], list[Odd]]:
        if not any(data):
            raise Exception('No details retrieved.')
        
        odds_to_create, odds_to_update = [], []
        allowed_selection_ids = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = self.odd_helper.get_existing_odds(self.sportsbook)

        def process_cell(cell, box_name, opp_name, home, away, home_abr, away_abr, match_id, existing_match_odds):
            odd_id = cell["id"]
            odds = cell["odd"]
            locked = not cell["active"]

            if odd_id in existing_match_odds:
                existing_odd = existing_match_odds.pop(odd_id)
                existing_odd.movement = self.get_movement(existing_odd.odd, odds)
                existing_odd.odd = odds
                existing_odd.locked = locked
                odds_to_update.append(existing_odd)
            else:
                cell_name = cell.get("name", "")
                description = f"{opp_name} {box_name} {cell_name}".strip()
                description = self.replace_by_tokens(description, [
                    (home, " *1* "),
                    (away, " *2* "),
                    (home_abr, " *1* "),
                    (away_abr, " *2* "),
                ]).replace("  ", " ").replace("  ", " ").strip()
                odds_to_create.append(OddModel(
                    id=None,
                    odd_id=odd_id,
                    code=0,
                    movement=1,
                    odd=odds,
                    is_default=self.sportsbook.is_default,
                    selected=False,
                    locked=locked,
                    event_id=match_id,
                    sportsbook_id=self.sportsbook.pk,
                    description=description,
                    market_id=""
                ))
                
        for dataset in filter(None, data): 
            try:
                match = dataset["matchPatches"]["patches"][0]["value"]
                match_id = match["id"]
                home, away = match["participantHome"], match["participantVisiting"]
                home_abr, away_abr = match["participantHomeAbbr"], match["participantVisitingAbbr"]
                existing_match_odds = existing_odds.get(match_id, {})

                for table in match.get("eventTables", []):
                    if table["mySelectionId"] not in allowed_selection_ids: 
                        continue
                    opp_name = table["name"]
                    for box in table["boxes"]:
                        box_name = box.get("name", "")
                        for cell in box["cells"]:
                            process_cell(cell, box_name, opp_name, home, away, home_abr, away_abr, match_id, existing_match_odds)  
            except Exception as ex: 
                print(f"Exception in map_odds Tipsport: {str(ex)}.")
                continue    

        return odds_to_create, odds_to_update

    def map_events_selected(self, events: list[Event], event_response: object) -> tuple[list[Event], list[Event]]:
        events_to_update, events_to_delete = [], []
        matches = event_response.get("patches", [{}])[0].get("value", {}).get("matches", [])
        retrieved_events = {match["id"]: match for match in matches}
        for event in events:
            try:
                match = retrieved_events.get(event.event_id, None)
                if match is None: 
                    events_to_delete.append(event)
                    continue
                event.time = match.get("score", {}).get("statusOffer", "")    
                events_to_update.append(event)  
            except Exception as ex:
                print(f"Exception in map_events_selected Tipsport: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def map_odds_selected(self, events: list[Event], odds_response: list[object])-> list[Odd]:
        event_dict = {event.event_id: event for event in events}
        odds_to_update: list[Odd] = []
        for data in filter(None, odds_response):
            try:
                match = data["matchPatches"]["patches"][0]["value"]
                event = event_dict.get(match["id"])
                if event:
                    odds_to_update.extend(self.update_selected_odds(event, match))
            except Exception as ex:
                print(f"Exception in map_odds_selected Tipsport: {str(ex)}.")
                continue                   
        
        return odds_to_update

    def update_selected_odds(self, event, match):
        bet_dict = {cell["id"]: cell for table in match.get("eventTables", []) for box in table["boxes"] for cell in box["cells"]}
        odds_to_update = []

        for odd in event.odds.filter(parent__selected=True).all(): 
            cell = bet_dict.get(odd.odd_id)
            if cell is None: 
                odd.locked = True
                odds_to_update.append(odd)
                continue
            odds = cell["odd"]
            odd.movement = self.get_movement(odd.odd, odds)      
            odd.odd = odds
            odd.locked = not cell["active"]
            odd.locked = True
            odds_to_update.append(odd)

        return odds_to_update
    
# NOTE: kto postupi a vitaz serie v hokeji su ta ista vec.