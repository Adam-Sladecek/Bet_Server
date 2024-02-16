from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class EventModel: 
    event_id: int
    sportsbook_id: int
    sport_id: int
    date_time: datetime
    first_name: str
    second_name: str

