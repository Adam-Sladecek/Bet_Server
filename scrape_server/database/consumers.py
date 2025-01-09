from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from enum import Enum
from jwt import decode as jwt_decode, ExpiredSignatureError, InvalidTokenError
import json
from queue import Queue
from rest_framework_simplejwt.tokens import UntypedToken
import threading

from database.enums import Command, DataType, TaskState
from database.Scrapes import scrape_fn

User = get_user_model()

@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()
    
class JWTAuthMiddleware:
    """ Custom middleware for WebSocket JWT Authentication """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = dict((x.split('=') for x in scope['query_string'].decode().split('&') if '=' in x))
        token = query_string.get('token')
        scope['user'] = AnonymousUser()
        
        if token:
            try:
                UntypedToken(token)
                decoded_data = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = decoded_data.get('user_id')
                scope['user'] = await get_user(user_id)
            except (ExpiredSignatureError, InvalidTokenError, KeyError):
                pass

        return await self.inner(scope, receive, send)
    
def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)

scrape_task_running = False
scrape_thread = None
scrape_event = None
send_all_event = None
import_queue = None

class ScrapeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'scrape_updates'
        if self.scope['user'].is_authenticated:
            await self.accept()
            global scrape_task_running, send_all_event
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.send_initial_status()
            await self.run_send_all()
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        if action in ['start', 'end', 'import', 'send_all']:
            await getattr(self, f"run_{action}")()
        else:
            await self.send_message(DataType.ERROR, "Invalid action")

    async def run_start(self):
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
                await self.run_send_all()
                return
            await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING)
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))

    async def run_end(self):
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

    async def run_send_all(self):
        try:
            global scrape_task_running, send_all_event
            if scrape_task_running: 
                send_all_event.set()
        except Exception as e:
            await self.send_message(DataType.ERROR, str(e))        

    async def send_initial_status(self):
        await self.send_message(DataType.IMPORTRUNNING, TaskState.CLOSED)
        await self.send_message(DataType.STATERESPONSE, TaskState.RUNNING if scrape_task_running else TaskState.CLOSED)

    async def send_message(self, type, data):
        if isinstance(data, Enum):
            data = data.value
        await self.send(json.dumps({'type': type.value, 'data': data}))

    async def group_message(self, request):
        await self.send_message(request["data_type"], request["data"])

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