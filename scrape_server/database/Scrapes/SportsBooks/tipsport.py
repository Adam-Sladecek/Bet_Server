import asyncio
from ..dataclass_models import EventModel, OddModel
from ..common import getCommonDriver
from ..scripts import get_existing_odds
from ...models import Odd, Event, Sport, SportsbookMarket
from .scraper import Scraper

class TipsportScraper(Scraper): 
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass    
        
    def get_driver(self):
        self.driver = getCommonDriver(False)
        url = "https://www.tipsport.sk/live"
        self.driver.get(url)

    def close_driver(self):
        try:
            self.driver.quit()
        except Exception as ex:
            print(f'Failed to quit tipsport driver. Exception: {str(ex)}')

    async def gather_events(self, sports: list[Sport]):
        url= "https://www.tipsport.sk/rest/offer/v1/live/in-play/entities"
        result = await self.execute_driver_script(url)
        return result
    
    async def gather_odds(self, events):
        tasks = []
        for event in events: 
            url = f"https://www.tipsport.sk/rest/offer/v3/live/matches/{event.event_id}/patches?withEventTables=true"
            tasks.append(asyncio.create_task(self.execute_driver_script(url)))
        results = await asyncio.gather(*tasks)
        return results
    
    def map_events(self, data: object) -> list[EventModel]: 
        events: list[EventModel] = []
        matches = data["patches"][0]["value"]["matches"]  
        sport_ids = self.get_sportids()
        for match in matches: 
            try:
                names = match["nameFull"].split(" - ")
                if len(names) != 2: continue
                
                sport_id = sport_ids.get(match["superSportId"], None)
                if sport_id is None: continue
                
                names = [name.strip() for name in names]
                time = match["score"]["statusOffer"] if "statusOffer" in match["score"] else ""
                events.append(EventModel(
                    id=None, 
                    event_id=match["id"], 
                    time =time, 
                    home=names[0], 
                    away=names[1], 
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
        odds_to_create: list[OddModel] = []
        odds_to_update: list[Odd] = []
        if all(element is None for element in data):
            raise Exception('No details retrieved.')
        
        allowed_selection_ids = set([sbmarket.value for sbmarket in SportsbookMarket.objects.filter(sportsbook=self.sportsbook).all()])
        existing_odds = get_existing_odds(self.sportsbook)
        for dataset in data: 
            if dataset is None: continue
            try:
                match = dataset["matchPatches"]["patches"][0]["value"]
                match_id = match["id"]
                home = match["participantHome"]
                away = match["participantVisiting"]
                home_abr = match["participantHomeAbbr"]
                away_abr = match["participantVisitingAbbr"]

                existing_match_odds = existing_odds[match_id]

                for table in match["eventTables"]:
                    if table["mySelectionId"] not in allowed_selection_ids: continue
                    opp_name = table["name"]
                    for box in table["boxes"]:
                        box_name = box["name"] if "name" in box else None
                        for cell in box["cells"]:
                            odd_id = cell["id"]
                            odds = cell["odd"]
                            locked = not cell["active"]
                            if odd_id in existing_match_odds: 
                                existing_odd = existing_match_odds[odd_id]
                                del existing_match_odds[odd_id]
                                existing_odd.movement = self.get_movement(existing_odd.odd, odds)
                                existing_odd.odd = odds
                                existing_odd.locked = locked
                                odds_to_update.append(existing_odd)
                                continue
                            cell_name = cell["name"]
                            if box_name is not None:
                                description = opp_name + " " + box_name + " " +  cell_name
                            else:
                                description = opp_name + " " +  cell_name

                            description = self.replace_by_tokens(description, [
                                (home, " *1* "),
                                (away, " *2* "),
                                (home_abr, " *1* "),
                                (away_abr, " *2* "),
                            ])
                            description = description.replace("  ", " ").replace("  ", " ").strip()
                            odds_to_create.append(OddModel(
                                id = None,
                                odd_id = odd_id,
                                code = 0,
                                movement = 1,
                                odd = odds,
                                is_default = self.sportsbook.is_default,
                                selected = False,
                                locked = locked, 
                                event_id = match_id,
                                sportsbook_id = self.sportsbook.pk,
                                description = description,
                                market_id = ""
                            ))   
                                 
            except Exception as ex: 
                print(f"Exception in map_odds Tipsport: {str(ex)}.")
                continue    

        return odds_to_create, odds_to_update

    def map_events_selected(self, events: list[Event], event_response: object) -> tuple[list[Event], list[Event]]:
        events_to_update: list[Event] = []
        events_to_delete: list[Event] = []
        matches = event_response["patches"][0]["value"]["matches"]  
        retrieved_events = {match["id"]: match for match in matches}
        for event in events:
            try:
                match = retrieved_events.get(event.event_id, None)
                if match is None: 
                    events_to_delete.append(event)
                    continue
                time = match["score"]["statusOffer"] if "statusOffer" in match["score"] else ""
                event.time = time    
                events_to_update.append(event)  
            except Exception as ex:
                print(f"Exception in map_events_selected Tipsport: {str(ex)}.")
                continue       
        
        return events_to_update, events_to_delete

    def map_odds_selected(self, events: list[Event], odds_response: list[object])-> list[Odd]:
        event_dict = {event.event_id: event for event in events}
        odds_to_update: list[Odd] = []
        for data in odds_response:
            try:
                if data is None: continue
                match = data["matchPatches"]["patches"][0]["value"]
                match_id = match["id"]
                event = event_dict[match_id]
                bet_dict = {}
                for table in match["eventTables"]:
                    for box in table["boxes"]:
                        for cell in box["cells"]:
                            bet_dict[cell["id"]] = cell
                for odd in event.odds.filter(parent__selected=True).all(): 
                    cell = bet_dict.get(odd.odd_id, None)
                    if cell is None: 
                        odd.locked = True
                        odds_to_update.append(odd)
                        continue
                    odds = cell["odd"]
                    odd.movement = self.get_movement(odd.odd, odds)      
                    odd.odd = odds
                    odd.locked = not cell["active"]
                    odds_to_update.append(odd)
            except Exception as ex:
                print(f"Exception in map_odds_selected Tipsport: {str(ex)}.")
                continue                   
        
        return odds_to_update

# NOTE: kto postupi a vitaz serie v hokeji su ta ista vec.