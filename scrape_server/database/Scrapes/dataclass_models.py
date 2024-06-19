from dataclasses import asdict, dataclass
from __future__ import annotations
from ..models import Opportunity, ParentOpportunity, Sport, Sportsbook
from collections import defaultdict

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

    @classmethod
    def dataclass_list_from_models(cls, models) -> list[Config]:
        return [cls(model.pk, model.name, model.selected) for model in models]
    
    @classmethod
    def dict_to_config(cls, item) -> Config:
        return cls(**item)

@dataclass(frozen=True)
class ConfigResponse: 
    sports: list[Config]
    sportsbooks: list[Config]

    @classmethod
    def dataclass_from_models(cls, sports: list[Sport], sportsbooks: list[Sportsbook]) -> ConfigResponse:
        sport_dataclasses = Config.dataclass_list_from_models(sports)
        sportsbook_dataclasses = Config.dataclass_list_from_models(sportsbooks)
        return cls(sport_dataclasses, sportsbook_dataclasses)
    
    @classmethod
    def dict_to_config_response(cls, dict_data) -> ConfigResponse:
        sports = [Config.dict_to_config(item) for item in dict_data.get('sports')]
        sportsbooks = [Config.dict_to_config(item) for item in dict_data.get('sportsbooks')]
        return cls(sports, sportsbooks)
    
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
    has_parent: bool

    @classmethod
    def dataclass_list_from_models(cls, opportunities: list[Opportunity]) -> list[OpportunityDataClass]:
        return [cls(opp.pk, opp.opp_description, opp.tip_type, opp.opp_number, opp.market_id, opp.bet_order, opp.sport.name, opp.sportsbook.name, opp.has_parent) for opp in opportunities]
    
    @classmethod
    def dict_to_dataclass_list(cls, dict_data) -> list[OpportunityDataClass]:
        return [cls(**opp) for opp in dict_data.get('opportunities')]
    
    @classmethod
    def dict_to_dataclass(cls, dict_data) -> OpportunityDataClass:
        return cls(**dict_data.get('opportunity'))

@dataclass(frozen=True)
class ParentOpportunityDataClass: 
    id: int
    description: str
    sport: str
    is_linked: bool

    @classmethod
    def dataclass_list_from_models(cls, parents: list[ParentOpportunity]) -> list[ParentOpportunityDataClass]:
        return [cls(parent.pk, parent.description, parent.sport.name, parent.is_linked) for parent in parents]
    
    @classmethod
    def dict_to_dataclass(cls, dict_data) -> ParentOpportunityDataClass:
        return cls(**dict_data.get('parent')) 
    
    @classmethod
    def dict_to_dataclass_list(cls, dict_data) -> list[ParentOpportunityDataClass]:
        return [cls(**opp) for opp in dict_data.get('parents')]
    
@dataclass(frozen=True)
class OpportunityFactoryResponse: 
    parents: list[ParentOpportunityDataClass]
    opportunities: list[OpportunityDataClass]

    @classmethod
    def data_class_from_models(cls, parents: list[ParentOpportunity], opportunities: list[Opportunity]) -> OpportunityFactoryResponse: 
        parent_dataclasses = ParentOpportunityDataClass.dataclass_list_from_models(parents)
        opp_dataclasses = OpportunityDataClass.dataclass_list_from_models(opportunities)
        return cls(parent_dataclasses, opp_dataclasses)

    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class OpportunityChildrenResponse: 
    parents: list[ParentOpportunityDataClass]
    opportunities: dict[int, list[OpportunityDataClass]]

    @classmethod
    def data_class_from_models(cls, parents: list[ParentOpportunity], opportunity_dict: dict[int, list[Opportunity]]) -> OpportunityChildrenResponse: 
        parent_dataclasses = ParentOpportunityDataClass.dataclass_list_from_models(parents)
        opportunity_dataclass_dict = defaultdict(list[OpportunityDataClass])
        for parent_id, opportunities in opportunity_dict.items(): 
            opportunity_dataclass_dict[parent_id] = OpportunityDataClass.dataclass_list_from_models(opportunities)
        return cls(parent_dataclasses, opportunity_dataclass_dict)

    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class OpportunityLinkDataClass: 
    sport: str
    parents: list[ParentOpportunityDataClass]

@dataclass(frozen=True)
class OpportunityLinkResponse: 
    links: list[OpportunityLinkDataClass]

    @classmethod
    def data_class_from_models(cls, parents: list[ParentOpportunity]) -> OpportunityLinkResponse: 
        used_ids = set()
        links = []
        for parent in parents: 
            if parent.pk in used_ids: continue
            linked_opp = parent.linked_opportunity
            link = OpportunityLinkDataClass(parent.sport.name, ParentOpportunityDataClass.dataclass_list_from_models([parent, linked_opp]))
            links.append(link)
            used_ids.add(parent.pk)
            used_ids.add(linked_opp.pk)
        return cls(links)

    @property
    def dict(self) -> dict:
        return asdict(self)    
    