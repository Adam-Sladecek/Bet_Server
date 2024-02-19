import queue
from .nike import nike_getData
from .tipsport import tipsport_getData
import asyncio
import threading
import logging 
import requests
from Models import ScrapeResultModel

def get_sportsbook_data(scrape_queue: queue.Queue, result_queue: queue.Queue, event: threading.Event, logger: logging.Logger): 
    try:
        targets = {
            'Doxxbet' : 1, 
            'Ifortuna': 1,
            'Tipos': 1,
            'Betfair': 1,
            'Nike': nike_getData,
            'Tipsport': tipsport_getData 
        }
        while True:
            if event.is_set():
                break
            try:
                request = scrape_queue.get(timeout=1)
            except queue.Empty:
                continue

            args = (request, result_queue, logger)
            asyncio.run(targets[request.sportsbook_name](*args, test=False))
        print('Done handling drivers.')  
    except Exception as ex:
        logger.error(str(ex))
        event.set()

def group_results(scrape_queue: queue.Queue, result_queue: queue.Queue, event: threading.Event, logger: logging.Logger, number_of_sportsbooks: int, tipos_included: bool): 
    try:
        result_dictionary = {}
        while True:
            if event.is_set():
                break
            try:
                result = result_queue.get(timeout=1)
            except queue.Empty:
                continue

            if type(result) is not ScrapeResultModel: 
                url = result.get('url')
                data = result.get('data')
                eventresponse = requests.post(url, json=data)
                continue
            if result.request.sport_id not in result_dictionary:
                result_dictionary[result.request.sport_id] = []
            result_dictionary[result.request.sport_id].append(result)    
            neccessaryCount = number_of_sportsbooks + 1 if (tipos_included and result.request.sport_type_id == 2) else number_of_sportsbooks
            if len(result_dictionary[result.request.sport_id]) == neccessaryCount:
                print("Scraping", result.request.sport_name)
                scrape_sport(result.request.sport_id, result.request.sport_name)
                for res in result_dictionary[result.request.sport_id]:
                    scrape_queue.put(res.request, block=True, timeout=None)
                result_dictionary[result.request.sport_id] = []
                       
        print('Getting results done.')  
    except Exception as ex:
        logger.error(str(ex))
        event.set()

def scrape_sport(sport_id: int, sport_name: str): 
    url = "http://127.0.0.1:5000/scrape"
    data = {
        'sport_id': sport_id
    }
    eventrespon = requests.get(url, params=data)
    print(f"End of scrape {sport_name}")    
