from enum import Enum
import threading
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Event
from .Scrapes import scrape_fn, import_job
from .enums import TaskState, DataType
from channels.layers import get_channel_layer
from django.conf import settings

scrape_task_running = False
import_thread: threading.Thread = None
class ScrapeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.group_name = 'scrape_updates'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        global scrape_task_running, import_thread
        await self.send_message(DataType.IMPORTRUNNING, TaskState.RUNNING if (import_thread is not None and import_thread.is_alive()) else TaskState.CLOSED)
        await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING if scrape_task_running else TaskState.CLOSED)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        global scrape_task_running
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
            global scrape_thread, scrape_event, scrape_task_running
            if not scrape_task_running:
                scrape_task_running = True
                scrape_event = threading.Event()
                scrape_thread = threading.Thread(target=scrape_fn, args=(scrape_event,))
                scrape_thread.start()
                await broadcast_message(DataType.STATERESPONSE, TaskState.RUNNING)
                return
            await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def end_scrape(self):
        try:
            global scrape_event, scrape_thread, scrape_task_running
            if scrape_task_running:
                scrape_task_running = False
                scrape_event.set()
                scrape_thread.join()
                await broadcast_message(DataType.STATERESPONSE, TaskState.CLOSED)
                return
            await self.send_message(DataType.STATERESPONSE, TaskState.CLOSED)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def run_import(self):
        try:
            global import_thread
            if import_thread is None or not import_thread.is_alive():
                import_thread = threading.Thread(target=import_job)
                import_thread.start()
                await broadcast_message(DataType.IMPORTRUNNING, TaskState.RUNNING)
                return
            await self.send_message(DataType.IMPORTRUNNING, TaskState.RUNNING)
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