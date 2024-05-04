from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class EventModel: 
    event_id: int
    date_time: str
    first_name: str
    second_name: str

@dataclass
class OddModel: 
    bet_id: int
    odd: float
    event_id: int
    market_id: str
    opp_description: str
    tip_type: str
    opp_number: str
    bet_order: int

@dataclass(frozen=True)
class RequestModel: 
    sport_name: str
    sport_id: int
    sport_type_id: int
    sportsbook_id: int
    sportsbook_name: str
    url: str
    is_tipos_more: bool

@dataclass(frozen=True)
class Config: 
    id: int
    name: str
    selected: bool

@dataclass(frozen=True)
class ConfigResponse: 
    sportsBooks: list[Config]
    sports: list[Config]

    @property
    def dict(self):
        return asdict(self)
    
    @staticmethod
    def dict_to_config(dict_data):
        return Config(**dict_data)
    
    @classmethod
    def dict_to_config_response(cls, dict_data):
        sports_books = [cls.dict_to_config(item) for item in dict_data.get('sportsBooks')]
        sports = [cls.dict_to_config(item) for item in dict_data.get('sports')]
        return cls(sportsBooks=sports_books, sports=sports)
    
@dataclass(frozen=True)
class UnassignedOpportunity: 
    opportunity_id: int
    opp_description: str
    tip_type: str
    opp_number: str
    market_id: str
    bet_order: int
    sport: str
    sportsbook: str

@dataclass(frozen=True)
class UnassignedOpportunityResponse: 
    data: dict[str, list[UnassignedOpportunity]] 

    @property
    def dict(self):
        return asdict(self)
    
    