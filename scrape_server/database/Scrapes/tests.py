from django.test import TestCase
import pytz
from .dataclass_models import EventModel
from datetime import datetime
from .scripts import update_events
from ..models import Event, Sport, Sportsbook, SportType

class ScrapeTest(TestCase):
    def setUp(self):
        self.sport_type = SportType.objects.create(name="WL")
        self.sport = Sport.objects.create(name="Soccer", selected=True, url="https://example.com", sport_type=self.sport_type)
        self.sportsbook = Sportsbook.objects.create(name="Sb A", selected=True, tenis_url="https://tennis.example.com")
        self.event_models = [
            EventModel(2, self.sport.pk, self.sportsbook.pk, datetime.isoformat(datetime.now(pytz.utc)), 'First name', 'Second name')
        ]

    def test_update_events(self):
        update_events(self.event_models, 1, 1)
        events = Event.objects.all()
        assert len(events) == 1 
        event = events[0]
        assert event.event_id == 2
        assert event.first_name == 'First name'
        assert event.second_name == 'Second name'
