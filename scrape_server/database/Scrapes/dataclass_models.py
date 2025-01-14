from __future__ import annotations
from dataclasses import asdict, dataclass
from database.models import Price, Opportunity, Sport, Sportsbook, Event, SportsbookMarket

@dataclass(frozen=True)
class EventModel: 
    id: int
    time: str
    description: str
    selected: bool
    sport_id: int
    sportsbook_id: int
    available_sportsbooks: list[int]
    price_count: int

    @classmethod
    def dataclass_list_from_models(cls, events: list[Event]) -> list[EventModel]:
        return [
        cls(
            id=event.pk,
            time=event.time,
            description=event.description,
            selected=event.selected,
            sport_id=event.sport.pk,
            sportsbook_id=event.sportsbook.pk,
            available_sportsbooks=[child.sportsbook.pk for child in event.children.all()],
            price_count=event.prices.count()
        )
        for event in events if event.children.exists()
    ]
    
@dataclass(frozen=True)
class EventResponse: 
    events: list[EventModel]
    
    @classmethod # prefetch prices, children, children__sportsbook, sportsbook, sport
    def dataclass_from_models(cls, events: list[Event]) -> EventResponse:
        dataclasses = EventModel.dataclass_list_from_models(events)
        return cls(events=dataclasses)

    @property
    def dict(self) -> dict:
        return asdict(self)
    
@dataclass(frozen=True)
class PriceResponse: 
    prices: list[PriceModel]
    
    @classmethod 
    def dataclass_from_models(cls, prices: list[Price], event: Event) -> PriceResponse:
        return cls(prices=[PriceModel.from_model(price, event) for price in prices])

    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class PriceModel:
    id: int = None
    description: str = None
    selected: bool = False
    price: Price = None

    @classmethod
    def from_model(cls, price: Price, event: Event) -> PriceModel:
        return cls(
            id = price.pk, 
            description = price.opportunity.description.replace('*1*', event.home).replace('*2*', event.away),
            selected = price.selected,
        )

@dataclass(frozen=True)
class MatchOpportunityResponse:
    opportunities: list[MatchOpportunity]
    update_all: bool
    match_ids: list[int]
    price_ids: list[int]

    @classmethod # prefetch sport, children, prices, prices__opportunity, prices__children, prices__children__sportsbook
    def dataclass_from_models(cls, events: list[Event], fetch_all: bool) -> MatchOpportunityResponse:
        price_ids = set()
        opportunities = MatchOpportunity.dataclass_list_from_models(events, price_ids, fetch_all)
        return cls(
            opportunities=opportunities, 
            update_all=fetch_all,
            match_ids=[event.pk for event in events],
            price_ids = list(price_ids)
        )
    
    @property
    def dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class MatchOpportunity:
    match_name: str
    opp_name: str
    match_id: int
    parent: MatchPrice
    child: MatchPrice
    sport_id: int
    sportsbook_id: int
    ev: float
    stake: float

    @classmethod
    def dataclass_list_from_models(cls, events: list[Event], price_ids: set, fetch_all: bool) -> list[MatchOpportunity]:
        result = []
        for event in events:
            match_name=event.description
            match_id=event.pk
            sport_id= event.sport.pk
            time = getattr(event.children.first(), 'time', event.time) 
            for price in event.prices.filter(selected=True, locked=False).order_by('id').all():
                parent_odds = float(price.odds)
                parent = MatchPrice(price.pk, parent_odds, price.locked, price.movement)
                opp_name = (
                    price.opportunity.description.replace('*1*', event.home).replace('*2*', event.away)
                    if price.opportunity_id else '', # comma needs to be here for some reason 
                )

                should_update_parent = price.should_be_updated()
                for childPrice in price.children.filter(event__used=False, locked=False).all():
                    should_update_child = childPrice.should_be_updated()
                    ev = childPrice.ev(parent_odds)
                    if ev > 0: 
                        price_ids.add(childPrice.pk)
                    if ev <= 0 or not (fetch_all or should_update_parent or should_update_child): 
                        continue
                    child = MatchPrice(childPrice.pk, float(childPrice.odds), childPrice.locked, childPrice.movement)
                    sportsbook_id = childPrice.sportsbook.pk
                    stake = childPrice.stake(parent_odds)
                    result.append(
                        cls(
                            match_name= match_name,
                            opp_name= opp_name, 
                            match_id= match_id,
                            parent= parent,
                            child= child,
                            sport_id = sport_id,
                            sportsbook_id = sportsbook_id,
                            ev = ev,
                            stake = stake
                        )
                    )
        return result

@dataclass(frozen=True)
class MatchPrice:
    price_pk: int
    odds: float
    locked: bool
    movement: int

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

    @classmethod
    def dataclass_list_from_models(cls, opportunities: list[Opportunity]) -> list[OpportunityDataClass]:
        return [
            cls(
                id=opp.pk, 
                description=opp.description, 
                is_default=opp.is_default, 
                prefered=opp.prefered, 
                sportsbook_id=opp.sportsbook.pk,
                sport_id=opp.sport.pk,
            ) for opp in opportunities
        ]
    
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
        result: list[OpportunityWithParentName] = [
            OpportunityWithParentName(
                parent_id=parent.pk,
                parent_name=parent.description,
                parent_prefered=parent.prefered,
                sportsbook_id=parent.sportsbook.pk,
                sport_id=parent.sport.pk,
                opportunity=model
            )
            for parent, opportunities in opportunity_touples
            for model in OpportunityDataClass.dataclass_list_from_models(opportunities)
        ]
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
    