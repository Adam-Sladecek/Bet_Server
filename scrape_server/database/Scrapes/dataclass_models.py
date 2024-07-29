from __future__ import annotations
from dataclasses import asdict, dataclass
from ..models import Odd, Opportunity, Sport, Sportsbook, Event

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
class OddResponse: 
    odds: list[OddModel]
    
    @classmethod
    def dataclass_from_models(cls, models: list[Odd]) -> OddResponse:
        odd_models = [OddModel.dataclass_from_model(model) for model in models]
        return cls(odds=odd_models)

    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class OddModel:
    id: int
    odd_id: int
    code: int
    movement: int
    odd: float
    is_default: bool
    selected: bool
    locked: bool
    event_id: int
    sportsbook_id: int
    description: str
    parent_id: int
    market_id: str

    @classmethod
    def dataclass_from_model(cls, odd: Odd) -> OddModel:
        return cls(
            id = odd.pk, 
            odd_id = odd.odd_id,
            code = odd.code,
            movement = odd.movement,
            odd = float(odd.odd),
            is_default = odd.is_default,
            selected = odd.selected,
            locked = odd.locked,
            event_id = odd.event.pk,
            sportsbook_id = odd.sportsbook.pk,
            description = odd.opportunity.description.replace('*1*', odd.event.home).replace('*2*', odd.event.away),
            parent_id = odd.parent if odd.parent is None else odd.parent.pk,
            market_id = odd.opportunity.market_id
            )

@dataclass(frozen=True)
class MatchResponse:
    matches: list[Match]
    sportsbook_ids: list[int]

    @classmethod
    def dataclass_from_models(cls, models: list[Event], sportsbooks: list[Sportsbook]) -> MatchResponse:
        return cls(
            matches=Match.dataclass_list_from_models(models), 
            sportsbook_ids= [sb.pk for sb in sportsbooks] 
            )
    
    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class Match:
    name: str
    match_id: int
    time: str
    sport_id: int
    opportunities: list[MatchOpportunity]

    @classmethod
    def dataclass_list_from_models(cls, models: list[Event]) -> list[Match]:
        return [cls(
            name=f"{event.home} vs. {event.away}", 
            match_id=event.pk,
            time = event.time,
            sport_id= event.sport.pk,
            opportunities = MatchOpportunity.dataclass_list_from_model(event)
            ) for event in models
        ]

@dataclass(frozen=True)
class MatchOpportunity:
    name: str
    odds: list[OddModel]

    @classmethod
    def dataclass_list_from_model(cls, model: Event) -> list[MatchOpportunity]:
        return [cls(
            name=odd.opportunity.description.replace('*1*', model.home).replace('*2*', model.away), 
            odds = [OddModel.dataclass_from_model(odd), *[OddModel.dataclass_from_model(child) for child in odd.children.all()]]
            ) for odd in model.odds.filter(selected=True).all()
        ]

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
    