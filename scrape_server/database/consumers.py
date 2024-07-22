from enum import Enum
import threading
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .Scrapes import scrape_fn
from .enums import TaskState, DataType, Command
from channels.layers import get_channel_layer
from queue import Queue

class ScrapeConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scrape_task_running = False
        self.scrape_thread = None
        self.scrape_event = None
        self.import_queue = None

    async def connect(self):
        await self.accept()
        self.group_name = 'scrape_updates'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.send_message(DataType.IMPORTRUNNING, TaskState.CLOSED)
        await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING if self.scrape_task_running else TaskState.CLOSED)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('action') == 'start':
            await self.start_scrape()
        elif data.get('action') == 'end':
            await self.end_scrape()
        elif data.get('action') == 'import':
            await self.run_import()
        else:
            await self.send_message(DataType.ERROR, "Invalid action")

    async def start_scrape(self):
        try:
            if not self.scrape_task_running:
                self.scrape_task_running = True
                self.scrape_event = threading.Event()
                self.import_queue = Queue(maxsize=2)
                self.scrape_thread = threading.Thread(target=scrape_fn, args=(self.scrape_event, self.import_queue))
                self.scrape_thread.start()
                await broadcast_message(DataType.STATERESPONSE, TaskState.RUNNING)
                return
            await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def end_scrape(self):
        try:
            if self.scrape_task_running:
                self.scrape_event.set()
                self.scrape_thread.join()
                self.scrape_task_running = False
                await broadcast_message(DataType.STATERESPONSE, TaskState.CLOSED)
                return
            await self.send_message(DataType.STATERESPONSE, TaskState.CLOSED)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def run_import(self):
        try:
            if not self.scrape_task_running: 
                await self.send_message(DataType.ERROR, "Start scrape before running import")
                return
            self.import_queue.put(Command.IMPORT)
            await broadcast_message(DataType.IMPORTRUNNING, TaskState.RUNNING)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def send_message(self, type, data):
        if isinstance(data, Enum):
            data = data.value
        await self.send(json.dumps({'type': type.value, 'data': data}))

    async def group_message(self, request):
        type = request["data_type"]    
        data = request["data"]  
        await self.send_message(type, data)

async def broadcast_message(data_type, data):
    if isinstance(data, Enum):
        data = data.value

    channel_layer = get_channel_layer()
    group_name = 'scrape_updates'
    await channel_layer.group_send(
        group_name,
        {
            'type': 'group_message',
            'data_type': data_type,
            'data': data,
        }
    )    