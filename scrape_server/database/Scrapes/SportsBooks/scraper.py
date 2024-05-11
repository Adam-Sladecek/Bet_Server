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

    def replace_by_tokens(self, text: str, replace_pairs: list[tuple[str, str]]) -> str:
        for str_to_replace, replace_tkn in replace_pairs:
            text = text.replace(str_to_replace, replace_tkn)
            space_indexes = [i for i, char in enumerate(str_to_replace) if char == ' ']
            for index in space_indexes:
                string_list = list(str_to_replace)
                string_list[index] = ''
                new_str_to_replace = ''.join(string_list)
                text = text.replace(new_str_to_replace, replace_tkn)
        return text    