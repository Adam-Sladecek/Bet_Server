import asyncio
from database.Scrapes.dataclass_models import PriceModel
from database.Scrapes.driver import Driver
from database.models import Price, Event, Sport
from database.Scrapes.SportsBooks.scraper import Scraper
from database.enums import Movement

class TipsportScraper(Scraper): 
    def get_driver(self) -> None:
        self.driver = Driver(False, "https://www.tipsport.sk/live")

    def close_driver(self) -> None:
        try:
            self.driver.close()
        except Exception as ex:
            print(f'Failed to quit tipsport driver. Exception: {str(ex)}')

    async def gather_events(self, sports: list[Sport]) -> object:
        url= "https://www.tipsport.sk/rest/offer/v1/live/in-play/entities"
        
        return await self.driver.execute_script(url)
    
    async def gather_prices(self, events: list[Event]) -> list[object]:
        tasks = [
            asyncio.create_task(
                self.driver.execute_script(
                    f"https://www.tipsport.sk/rest/offer/v3/live/matches/{event.event_id}/patches?withEventTables=true"
                )
            ) for event in events
        ]
        return await asyncio.gather(*tasks)
    
    def map_events(self, data: object) -> list[Event]: 
        events = []
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
                events.append(Event(
                    event_id=match["id"], 
                    time=time, 
                    home=home, 
                    away=away, 
                    is_default=self.sportsbook.is_default, 
                    sportsbook=self.sportsbook, 
                    sport_id=sport_id,
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
    
    def map_prices(self, events: list[Event], data: list[object]) -> tuple[list[PriceModel], list[Price]]:
        prices_to_create, prices_to_update = [], []

        for event in events: 
            dataset = next((d for d in data if self.get_match(d).get("id") == event.event_id), None)
            if dataset is None: 
                for price in event.prices.all():
                    price.locked = True
                    prices_to_update.append(price)
                continue
            
            match = self.get_match(dataset)
            home, away = match["participantHome"], match["participantVisiting"]
            home_abr, away_abr = match["participantHomeAbbr"], match["participantVisitingAbbr"]

            bet_dict = {}
            for table in match.get("eventTables", []):
                if table["mySelectionId"] not in self.allowed_markets: 
                    continue
                opp_name = table["name"]
                for box in table["boxes"]:
                    box_name = box.get("name", "")
                    for cell in box["cells"]:
                        price_id = cell.get("id")
                        bet_dict[price_id] = (opp_name, box_name, cell)
        
            # Update existing prices
            for price in event.prices.all():
                _, _, cell = bet_dict.pop(price.price_id, (None, None, None))
                self.update_price(price, cell)
                prices_to_update.append(price)

            # Create new prices
            for price_id, (opp_name, box_name, cell) in bet_dict.items():
                price = self.create_new_price(event, price_id, cell, opp_name, box_name, home, away, home_abr, away_abr)
                if price:
                    prices_to_create.append(price)

        return prices_to_create, prices_to_update
    
    def get_match(self, data: list[object]) -> dict:
        if not data:
            return {}
        return data.get("matchPatches", {}).get("patches", [{}])[0].get("value", {})

    def extract_cell_details(self, cell: object) -> tuple[float, bool, str]:
        return (cell.get("odd"), not cell.get("active", False), cell.get("name", ""))

    def update_price(self, price: Price, cell: object) -> None:
        if not cell:
            price.locked = True
            return
        
        odds, locked, _ = self.extract_cell_details(cell)
        price.movement = self.get_movement(price.odds, odds)
        price.odds = odds
        price.locked = locked
    
    def create_new_price(self, event: Event, price_id: int, cell: object, opp_name: str, box_name: str, home: str, away: str, home_abr: str, away_abr: str) -> PriceModel | None:
        try:
            odds, locked, cell_name = self.extract_cell_details(cell)
            description = f"{opp_name} {box_name} {cell_name}".strip()
            description = self.replace_by_tokens(description, [
                (home, " *1* "),
                (away, " *2* "),
                (home_abr, " *1* "),
                (away_abr, " *2* "),
            ]).replace("  ", " ").replace("  ", " ").strip()

            price = Price(
                price_id = price_id,
                movement = Movement.UP.value,
                odds = odds,
                is_default = self.sportsbook.is_default,
                selected = True,
                locked = locked,
                event = event,
                sportsbook = self.sportsbook,
            )

            return PriceModel(description=description, price=price)
        except Exception as ex:
            print(f"Exception in create_new_price description Tipsport: {str(ex)}.")
            return None

# NOTE: kto postupi a vitaz serie v hokeji su ta ista vec.