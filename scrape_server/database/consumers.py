from enum import Enum
import threading
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .Scrapes import scrape_fn
from .enums import TaskState, DataType, Command
from channels.layers import get_channel_layer
from queue import Queue

scrape_task_running = False
scrape_thread = None
scrape_event = None
send_all_event = None
import_queue = None
class ScrapeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.group_name = 'scrape_updates'
        global scrape_task_running, send_all_event
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.send_message(DataType.IMPORTRUNNING, TaskState.CLOSED)
        await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING if scrape_task_running else TaskState.CLOSED)
        await self.set_send_all_event()

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
        elif data.get('action') == 'send_all':
            await self.set_send_all_event()
        else:
            await self.send_message(DataType.ERROR, "Invalid action")

    async def start_scrape(self):
        try:
            global scrape_task_running, scrape_event, import_queue, scrape_thread, send_all_event
            if not scrape_task_running:
                scrape_task_running = True
                scrape_event = threading.Event()
                send_all_event = threading.Event()
                import_queue = Queue(maxsize=2)
                scrape_thread = threading.Thread(target=scrape_fn, args=(scrape_event, import_queue, send_all_event))
                scrape_thread.start()
                await broadcast_message(DataType.STATERESPONSE, TaskState.RUNNING)
                return
            await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def end_scrape(self):
        try:
            global scrape_task_running, scrape_event, scrape_thread
            if scrape_task_running:
                scrape_event.set()
                scrape_thread.join()
                scrape_task_running = False
                await broadcast_message(DataType.STATERESPONSE, TaskState.CLOSED)
                return
            await self.send_message(DataType.STATERESPONSE, TaskState.CLOSED)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def run_import(self):
        try:
            global scrape_task_running, import_queue
            if not scrape_task_running: 
                await self.send_message(DataType.ERROR, "Start scrape before running import")
                return
            import_queue.put(Command.IMPORT)
            await broadcast_message(DataType.IMPORTRUNNING, TaskState.RUNNING)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def set_send_all_event(self):
        try:
            global scrape_task_running, send_all_event
            if scrape_task_running: 
                send_all_event.set()
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