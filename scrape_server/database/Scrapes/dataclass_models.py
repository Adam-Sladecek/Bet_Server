from __future__ import annotations
from dataclasses import asdict, dataclass, field
from ..models import Odd, Opportunity, Sport, Sportsbook, Event, SportsbookMarket
from typing import Optional

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
    available_sportsbooks: list[int]
    odd_count: int

    @classmethod
    def dataclass_list_from_models(cls, events: list[Event]) -> list[EventModel]:
        return [cls(id=event.pk, 
                    event_id=event.event_id, 
                    time=event.time, 
                    home=event.home, 
                    away=event.away, 
                    is_default=event.is_default, 
                    selected=event.selected, 
                    sportsbook_id=event.sportsbook.pk, 
                    sport_id=event.sport.pk,
                    available_sportsbooks=[child.sportsbook.pk for child in event.children.all()],
                    odd_count=event.odds.count()) for event in events]

@dataclass(frozen=True)
class EventResponse: 
    events: list[EventModel]
    
    @classmethod # prefetch sportsbook, sport, children, children__sportsbook
    def dataclass_from_models(cls, events: list[Event]) -> EventResponse:
        dataclasses = EventModel.dataclass_list_from_models(events)
        return cls(events=dataclasses)

    @property
    def dict(self) -> dict:
        return asdict(self)
    
@dataclass(frozen=True)
class OddResponse: 
    odds: list[OddModel]
    
    @classmethod # prefetch sportsbook, opportunity
    def dataclass_from_models(cls, odds: list[Odd], event: Event) -> OddResponse:
        odd_models = [OddModel.dataclass_from_model(odd, event) for odd in odds]
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
    market_id: str
    kelly: Optional[float] = field(default=None)

    @classmethod
    def dataclass_from_model(cls, odd: Odd, event: Event) -> OddModel:
        odds = float(odd.to_decimal())
        kelly = None if odd.is_default else odd.kelly(odds)
        return cls(
            id = odd.pk, 
            odd_id = odd.odd_id,
            code = odd.code,
            movement = odd.movement,
            odd = odds,
            is_default = odd.is_default,
            selected = odd.selected,
            locked = odd.locked,
            event_id = event.pk,
            sportsbook_id = odd.sportsbook.pk,
            description = odd.opportunity.description.replace('*1*', event.home).replace('*2*', event.away),
            market_id = odd.opportunity.market_id,
            kelly = kelly
            )

@dataclass(frozen=True)
class MatchOpportunityResponse:
    opportunities: list[MatchOpportunity]
    update_all: bool
    match_ids: list[int]
    sportsbook_ids: list[int]

    @classmethod # prefetch sport, children, odds, odds__opportunity, odds__children, odds__children__opportunity, odds__children__sportsbook
    def dataclass_from_models(cls, events: list[Event], sportsbooks: list[Sportsbook], fetch_all: bool) -> MatchOpportunityResponse:
        return cls(
            opportunities=MatchOpportunity.dataclass_list_from_models(events, fetch_all), 
            update_all=fetch_all,
            match_ids=[event.pk for event in events],
            sportsbook_ids= [sb.pk for sb in sportsbooks] 
            )
    
    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class MatchOpportunity:
    name: str
    match_name: str
    match_id: int
    odd_id: int
    time: str
    sport_id: int
    odds: list[OddModel]

    @classmethod
    def dataclass_list_from_models(cls, events: list[Event], fetch_all: bool) -> list[MatchOpportunity]:
        result = []
        for event in events:
            match_name=f"{event.home} vs. {event.away}"
            match_id=event.pk
            time = event.children.first().time if event.children.count() > 0 else event.time # time consuming
            sport_id= event.sport.pk
            odds = [odd for odd in event.odds.filter(selected=True).order_by('id').all() if fetch_all or odd.should_be_updated()]
            if len(odds) == 0 : 
                result.append(cls(
                    name='', 
                    match_name= match_name,
                    match_id= match_id,
                    odd_id= match_id,
                    time= time,
                    sport_id=sport_id,
                    odds = []
                    ))
                continue
            result.extend([cls(
                name=odd.opportunity.description.replace('*1*', event.home).replace('*2*', event.away) if odd.opportunity_id else '', 
                match_name= match_name,
                match_id= match_id,
                odd_id= odd.pk,
                time= time,
                sport_id=sport_id,
                odds = [OddModel.dataclass_from_model(odd, event), 
                    *[OddModel.dataclass_from_model(child, event) for child in odd.children.all()]] 
                ) for odd in odds
                ])
        return result

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
    prefered: bool
    sportsbook_id: int
    sport_id: int
    market_id: str

    @classmethod
    def dataclass_list_from_models(cls, opportunities: list[Opportunity]) -> list[OpportunityDataClass]:
        return [cls(
            id=opp.pk, 
            description=opp.description, 
            is_default=opp.is_default, 
            prefered=opp.prefered, 
            sportsbook_id=opp.sportsbook.pk,
            sport_id=opp.sport.pk,
            market_id=opp.market_id) for opp in opportunities]
    
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

    @classmethod # prefetch sportsbook, sport
    def data_class_from_models(cls, parents: list[Opportunity], opportunities: list[Opportunity]) -> OpportunityFactoryResponse: 
        parent_dataclasses = OpportunityDataClass.dataclass_list_from_models(parents)
        opp_dataclasses = OpportunityDataClass.dataclass_list_from_models(opportunities)
        return cls(parents=parent_dataclasses, opportunities=opp_dataclasses)
        
    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class OpportunityWithParentName: 
    parent_id: int
    parent_name: str
    parent_prefered: bool
    sportsbook_id: int
    sport_id: int
    opportunity: OpportunityDataClass

@dataclass(frozen=True)
class OpportunityChildrenResponse: 
    opportunities: list[OpportunityWithParentName]

    @classmethod # prefetch sportsbook, sport, 
    def data_class_from_models(cls, opportunity_touples: list[tuple[Opportunity, list[Opportunity]]]) -> OpportunityChildrenResponse: 
        result: list[OpportunityWithParentName] = []
        for parent, opportunities in opportunity_touples: 
            models = OpportunityDataClass.dataclass_list_from_models(opportunities)
            for model in models: 
                result.append(OpportunityWithParentName(
                    parent_id=parent.pk,
                    parent_name=parent.description,
                    parent_prefered=parent.prefered,
                    sportsbook_id=parent.sportsbook.pk,
                    sport_id=parent.sport.pk,
                    opportunity=model))
        return cls(opportunities=result)

    @property
    def dict(self) -> dict:
        return asdict(self)
    
@dataclass(frozen=True)
class Market: 
    id: int
    name: str

    @classmethod
    def data_class_list_from_models(cls, markets: list[SportsbookMarket]) -> list[Market]: 
        return [cls(id=market.pk, name=market.value) for market in markets]
    
@dataclass(frozen=True)
class SbWithMarkets: 
    sportsbook_id: int
    markets: list[Market]

    @classmethod
    def data_class_from_models(cls, sportsbook: Sportsbook) -> SbWithMarkets:
        result = Market.data_class_list_from_models(sportsbook.markets.all()) 
        return cls(sportsbook_id=sportsbook.pk, markets=result)
    
@dataclass(frozen=True)
class MarketResponse: 
    sb_markets: list[SbWithMarkets]

    @classmethod # prefetch markets 
    def data_class_from_models(cls, sportsbooks: list[Sportsbook]) -> MarketResponse: 
        result = [SbWithMarkets.data_class_from_models(sportsbook) for sportsbook in sportsbooks]
        return cls(sb_markets=result)

    @property
    def dict(self) -> dict:
        return asdict(self)    
    