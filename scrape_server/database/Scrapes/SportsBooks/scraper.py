from abc import ABC, abstractmethod
import json
import aiohttp 
import asyncio
from ..dataclass_models import RequestModel
from datetime import datetime

class Scraper(ABC):
    @abstractmethod
    def import_all_data(self):
        pass

    @abstractmethod
    async def gather_events(self):
        pass

    @abstractmethod
    async def gather_odds(self):
        pass

    @abstractmethod
    def map_events(self):
        pass

    # @abstractmethod
    # def map_odds(self):
    #     pass

    # @abstractmethod
    # def get_data(self):
    #     pass

    async def gather_data(self, data: list[tuple[str, RequestModel]]) -> list[tuple[object, RequestModel]]:
        async with aiohttp.ClientSession() as session:
            tasks = [asyncio.create_task(self.fetch_data(session, url, request)) for url, request in data]
            return await asyncio.gather(*tasks)

    async def fetch_data(self, session: aiohttp.ClientSession, url:str, request: RequestModel) -> tuple[object, RequestModel]:
        async with session.get(url) as resp:
            result = await resp.json()    
            return (result, request)
        
    def convert_timestamp_to_time_string(self, timestamp_ms):
            current_time = datetime.now()
            timestamp_s = timestamp_ms / 1000
            timestamp_time = datetime.fromtimestamp(timestamp_s)
            time_difference = current_time - timestamp_time
            total_seconds = int(time_difference.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02}'"

    # async def execute_driver_script(self, driver, script: str): 
    #     try:
    #         driver.execute_script(script)
    #         response_data = driver.execute_script("return window.responseData;")
    #         return json.loads(response_data)
    #     except Exception as ex:
    #         return None

    # def replace_by_tokens(self, text: str, replace_pairs: list[tuple[str, str]]) -> str:
    #     for str_to_replace, replace_tkn in replace_pairs:
    #         text = text.replace(str_to_replace, replace_tkn)
    #         space_indexes = [i for i, char in enumerate(str_to_replace) if char == ' ']
    #         for index in space_indexes:
    #             string_list = list(str_to_replace)
    #             string_list[index] = ''
    #             new_str_to_replace = ''.join(string_list)
    #             text = text.replace(new_str_to_replace, replace_tkn)
    #     return text    