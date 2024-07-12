from __future__ import annotations
from dataclasses import asdict, dataclass
from ..models import Opportunity, Sport, Sportsbook, Event

@dataclass(frozen=True)
class EventModel: 
    id: int
    event_id: int
    time: str
    home: str
    away: str
    is_default: bool
    selected: bool
    sportsbook_id: int
    sport_id: int
    parent_id: int

    @classmethod
    def dataclass_list_from_models(cls, models: list[Event]) -> list[EventModel]:
        return [cls(id=model.pk, 
                    event_id=model.event_id, 
                    time=model.time, 
                    home=model.home, 
                    away=model.away, 
                    is_default=model.is_default, 
                    selected=model.selected, 
                    sportsbook_id=model.sportsbook.pk, 
                    sport_id=model.sport.pk,
                    parent_id=None if model.parent is None else model.parent.pk) for model in models]

@dataclass(frozen=True)
class EventResponse: 
    events: list[EventModel]
    
    @classmethod
    def dataclass_from_models(cls, models) -> EventResponse:
        events = EventModel.dataclass_list_from_models(models)
        return cls(events=events)

    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class OddModel: 
    id: int
    odd_id: int
    code: int
    odd: float
    is_default: bool
    selected: bool
    locked: bool
    event_id: int
    sportsbook_id: int
    description: str
    parent_id: int
    market_id: str
   
@dataclass(frozen=True)
class RequestModel: 
    sport_id: int
    sport_name: str
    sportsbook_id: int
    sportsbook_name: str
    is_default: bool
    url: str

    @classmethod
    def dataclass_list_from_models(cls, sb: Sportsbook, sports: list[Sport]) -> list[RequestModel]:
        return [cls(sport_id=sport.pk, sport_name=sport.name, sportsbook_id=sb.pk, sportsbook_name=sb.name, is_default=sb.is_default, url=getattr(sb, sport.url)) for sport in sports]

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
    description: str
    is_default: bool
    sportsbook: str
    sport: str
    parent_id: int

    @classmethod
    def dataclass_list_from_models(cls, opportunities: list[Opportunity]) -> list[OpportunityDataClass]:
        return [cls(id=opp.pk, description=opp.description, tip_type=opp.tip_type, is_default=opp.is_default, sportsbook=opp.sportsbook.name) for opp in opportunities]
    
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
    