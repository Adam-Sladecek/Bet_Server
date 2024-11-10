import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'scrape_server.settings'
django.setup()

from channels.testing import WebsocketCommunicator
from unittest.mock import patch, AsyncMock
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from database.consumers import broadcast_message
from database.enums import DataType, TaskState
from django.test import TestCase
from scrape_server.asgi import application

class TestConsumer(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.first() or User.objects.create_user(username='testuser', password='password')
        refresh = RefreshToken.for_user(user)
        cls.token = str(refresh.access_token)
    
    @patch('threading.Thread')
    @patch('threading.Event')
    async def test_receive_start_end_scrape(self, thread_mock, event_mock):
        communicator = await self.connect_communicator()
        await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED)
        await communicator.send_json_to({"action": "start"})
        await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.RUNNING)

        assert event_mock.called, 'Event should be called.'
        assert thread_mock.called, 'Scrape thread should be called.'

        await communicator.send_json_to({"action": "start"})
        await self.should_receive(communicator,DataType.STATERESPONSE, TaskState.RUNNING)

        await communicator.send_json_to({"action": "startxx"})
        await self.should_receive_error(communicator, DataType.ERROR, "Invalid action")

        communicator2 = await self.connect_communicator()
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.RUNNING)

        await communicator2.send_json_to({"action": "end"})
        await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED) 
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED) 

        await communicator.send_json_to({"action": "end"})
        await self.should_receive(communicator, DataType.STATERESPONSE, TaskState.CLOSED)
        await communicator.disconnect()
        await communicator2.disconnect()

    async def test_broadcast_message(self):
        communicator1 = await self.connect_communicator()
        await self.should_receive(communicator1, DataType.STATERESPONSE, TaskState.CLOSED)
        communicator2 = await self.connect_communicator()
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED)

        await broadcast_message(DataType.STATERESPONSE, TaskState.CLOSED)
        await self.should_receive(communicator1, DataType.STATERESPONSE, TaskState.CLOSED)
        await self.should_receive(communicator2, DataType.STATERESPONSE, TaskState.CLOSED)

        await communicator1.disconnect()
        await communicator2.disconnect()

    async def connect_communicator(self):
        mock_user = AsyncMock()
        mock_user.is_authenticated = True
        with patch('database.consumers.get_user', return_value=mock_user):
            communicator = WebsocketCommunicator(
                application, 
                f"/ws/scrape/?token={self.token}"
            )
            connected, _ = await communicator.connect()
            assert connected, 'Should be connected'
            await self.should_receive(communicator, DataType.IMPORTRUNNING, TaskState.CLOSED)
            return communicator
    
    async def should_receive(self, communicator: WebsocketCommunicator, expected_type: DataType, expected_state: TaskState):
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], expected_type.value)
        self.assertEqual(response["data"], expected_state.value)

    async def should_receive_error(self, communicator: WebsocketCommunicator, expected_type: DataType, error: str):
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], expected_type.value)
        self.assertEqual(response["data"], error)    