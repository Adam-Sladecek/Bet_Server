from abc import ABC, abstractmethod
import json
import aiohttp 
import asyncio

class Scraper(ABC):
    @abstractmethod
    async def gather_events(self):
        pass

    @abstractmethod
    async def gather_details(self):
        pass

    @abstractmethod
    def map_events(self):
        pass

    @abstractmethod
    def map_odds(self):
        pass

    @abstractmethod
    def get_data(self):
        pass

    async def gather_data(self, urls: list[str]):
        async with aiohttp.ClientSession() as session:
            tasks = [asyncio.create_task(self.fetch_data(session, url)) for url in urls]
            return await asyncio.gather(*tasks)

    async def fetch_data(self, session: aiohttp.ClientSession, url:str):
        async with session.get(url) as resp:
            result = await resp.json()    
            return result

    async def execute_driver_script(self, driver, script: str): 
        try:
            driver.execute_script(script)
            response_data = driver.execute_script("return window.responseData;")
            return json.loads(response_data)
        except:
            return None
