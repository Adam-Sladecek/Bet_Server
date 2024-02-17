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

@dataclass
class OddModel: 
    bet_id: int
    odd: int
    event_id: int
    sportsbook_id: int
    market_id: str
    opp_description: str
    tip_type: str
    opp_number: str
    bet_order: int
    opportunity_id: int 
