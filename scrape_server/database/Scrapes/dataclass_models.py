from __future__ import annotations
from dataclasses import asdict, dataclass
from ..models import Opportunity, Sport, Sportsbook
from datetime import time, datetime

@dataclass(frozen=True)
class EventModel: 
    event_id: int
    date_time: datetime
    first_name: str
    second_name: str

@dataclass(frozen=True)
class DefaultEvent: 
    id: int
    time: time
    first_name: str
    second_name: str
    sport: str
    selected: bool

    @classmethod
    def dataclass_list_from_models(cls, models) -> list[DefaultEvent]:
        return [cls(id=model.pk, name=model.time, first_name=model.first_name, second_name=model.second_name, sport=model.sport.name, selected=model.selected) for model in models]

@dataclass(frozen=True)
class DefaultEventResponse: 
    events: list[DefaultEvent]
    
    @classmethod
    def dataclass_from_models(cls, models) -> DefaultEventResponse:
        events = DefaultEvent.dataclass_list_from_models(models)
        return cls(events=events)

    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class EventOdd: 
    id: int
    odd: float
    description: str
    second_name: str
    sport: str
    selected: bool

@dataclass(frozen=True)
class EventOddsResponse: 
    odds: list[EventOdd]
    
    @classmethod
    def dataclass_from_models(cls, models) -> EventOddsResponse:
        events = EventOdd.dataclass_list_from_models(models)
        return cls(events=events)

    @property
    def dict(self) -> dict:
        return asdict(self)
    
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

    @classmethod
    def dataclass_list_from_models(cls, models) -> list[Config]:
        return [cls(id=model.pk, name=model.name, selected=model.selected) for model in models]
    
    @classmethod
    def dict_to_config(cls, item) -> Config:
        return cls(**item)

@dataclass(frozen=True)
class ConfigResponse: 
    sports: list[Config]
    sportsbooks: list[Config]
    default_sportsbooks: list[Config]

    @classmethod
    def dataclass_from_models(cls, sports: list[Sport], sportsbooks: list[Sportsbook], default_sportsbooks: list[Sportsbook]) -> ConfigResponse:
        sport_dataclasses = Config.dataclass_list_from_models(sports)
        sportsbook_dataclasses = Config.dataclass_list_from_models(sportsbooks)
        default_sportsbook_dataclasses = Config.dataclass_list_from_models(default_sportsbooks)
        return cls(sports=sport_dataclasses, sportsbooks=sportsbook_dataclasses, default_sportsbooks=default_sportsbook_dataclasses)
    
    @classmethod
    def dict_to_config_response(cls, dict_data) -> ConfigResponse:
        sports = [Config.dict_to_config(item) for item in dict_data.get('sports')]
        sportsbooks = [Config.dict_to_config(item) for item in dict_data.get('sportsbooks')]
        default_sportsbooks = [Config.dict_to_config(item) for item in dict_data.get('default_sportsbooks')]
        return cls(sports=sports, sportsbooks=sportsbooks, default_sportsbooks=default_sportsbooks)
    
    @property
    def dict(self) -> dict:
        return asdict(self)
    
@dataclass(frozen=True)
class OpportunityDataClass: 
    id: int
    opp_description: str
    tip_type: str
    opp_number: str
    market_id: str
    bet_order: int
    sport: str
    sportsbook: str
    is_default: bool

    @classmethod
    def dataclass_list_from_models(cls, opportunities: list[Opportunity]) -> list[OpportunityDataClass]:
        return [cls(id=opp.pk, opp_description=opp.opp_description, tip_type=opp.tip_type, opp_number=opp.opp_number, market_id=opp.market_id, bet_order=opp.bet_order, sport=opp.sport.name, sportsbook=opp.sportsbook.name) for opp in opportunities]
    
    @classmethod
    def dict_to_dataclass_list(cls, dict_data) -> list[OpportunityDataClass]:
        return [cls(**opp) for opp in dict_data.get('opportunities')]
    
    @classmethod
    def dict_to_dataclass(cls, dict_data) -> OpportunityDataClass:
        return cls(**dict_data.get('opportunity'))
    
@dataclass(frozen=True)
class OpportunityFactoryResponse: 
    parents: list[OpportunityDataClass]
    opportunities: list[OpportunityDataClass]

    @classmethod
    def data_class_from_models(cls, parents: list[Opportunity], opportunities: list[Opportunity]) -> OpportunityFactoryResponse: 
        parent_dataclasses = OpportunityDataClass.dataclass_list_from_models(parents)
        opp_dataclasses = OpportunityDataClass.dataclass_list_from_models(opportunities)
        return cls(parents=parent_dataclasses, opportunities=opp_dataclasses)

    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class OpportunityWithParentName: 
    parent_name: str
    opportunity: OpportunityDataClass

@dataclass(frozen=True)
class OpportunityChildrenResponse: 
    opportunities: list[OpportunityWithParentName]

    @classmethod
    def data_class_from_models(cls, opportunity_dict: dict[str, list[Opportunity]]) -> OpportunityChildrenResponse: 
        result: list[OpportunityWithParentName] = []
        for parent_description, opportunities in opportunity_dict.items(): 
            models = OpportunityDataClass.dataclass_list_from_models(opportunities)
            for model in models: 
                result.append(OpportunityWithParentName(parent_name=parent_description, opportunity=model))
        return cls(opportunities=result)

    @property
    def dict(self) -> dict:
        return asdict(self)
    