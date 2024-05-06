from dataclasses import asdict, dataclass

from ..models import Opportunity, OpportunityLink

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
    opportunity_tbl_id: int
    opp_description: str
    tip_type: str
    opp_number: str
    market_id: str
    bet_order: int
    sport: str
    sportsbook: str

    @classmethod
    def dict_to_UO_list(cls, dict_data):
        return [cls(**opp) for opp in dict_data.get('opportunities')]
    
@dataclass(frozen=True)
class UnassignedOpportunityResponse: 
    data: dict[str, list[UnassignedOpportunity]] 

    @property
    def dict(self):
        return asdict(self)
    
@dataclass(frozen=True)
class OpportunityDataClass: 
    sportsbook: str
    opp_description: str   
    tip_type: str   
    opp_number: str   
    market_id: str   
    bet_order: int   
    sport: str   

@dataclass(frozen=True)
class OpportunityLinkResponse: 
    opportunity_link_id: int
    opportunities: list[OpportunityDataClass]

@dataclass(frozen=True)
class OpportunityLinkResponseDict: 
    data: list[OpportunityLinkResponse] 

    @property
    def dict(self):
        return asdict(self)
    
    @classmethod
    def opp_link_to_OL_dict(cls, opportunity_links: list[OpportunityLink]):
        results = []
        for opportunity_link in opportunity_links:
            first_opp: Opportunity = opportunity_link.first_opportunity
            second_opp: Opportunity = opportunity_link.second_opportunity
            data = [
                OpportunityDataClass(
                    opp.sportsbook.name, 
                    opp.opp_description, 
                    opp.tip_type,
                    opp.opp_number,
                    opp.market_id,
                    opp.bet_order,
                    opp.sport.name
                ) for opp in [first_opp, second_opp]
            ]
            results.append(OpportunityLinkResponse(opportunity_link.pk, data))
        return cls(results)   