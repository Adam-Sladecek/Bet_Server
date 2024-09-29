from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class SportPS3838: 
    id: int
    name: str
    hasOfferings: bool
    leagueSpecialsCount: int
    eventSpecialsCount: int
    eventCount: int

    @classmethod
    def dataclass_list_from_models(cls, json: object) -> list[SportPS3838]:
        return [cls(**sport) for sport in json['sports']]
    
@dataclass(frozen=True)
class FixturePS3838: 
    sportId: int
    last: int
    league: list[LeaguePS3838]

    @classmethod
    def dataclass_from_model(cls, json: object) -> FixturePS3838:
        return cls (
            sportId=json['sportId'],
            last=json['last'],
            leaque= LeaguePS3838.dataclass_list_from_models(json['leaque'])
        )

@dataclass(frozen=True)
class LeaguePS3838: 
    id: int
    name: str
    events: list[EventPS3838]

    @classmethod
    def dataclass_list_from_models(cls, objects: list[object]) -> list[LeaguePS3838]:
        return [cls(
            id= obj['id'],
            name= obj['name'],
            events= EventPS3838.dataclass_list_from_models(obj['events'])
        ) for obj in objects]        

@dataclass(frozen=True)
class EventPS3838: 
    id: int
    starts: str
    home: str
    away: str
    rotNum: int
    liveStatus: int
    status: str
    parlayRestriction: int
    parentId: int
    altTeaser: bool
    resultingUnit: str
    betAcceptanceType: int
    version: int

    @classmethod
    def dataclass_list_from_models(cls, objects: list[object]) -> list[EventPS3838]:
        return [cls(**obj) for obj in objects]
    
@dataclass(frozen=True)
class PeriodPS3838: 
    number: int
    description: str
    shortDescription: str
    spreadDescription: str
    moneylineDescription: str
    totalDescription: str
    team1TotalDescription: str
    team2TotalDescription: str
    spreadShortDescription: str
    moneylineShortDescription: str
    totalShortDescription: str
    team1TotalShortDescription: str
    team2TotalShortDescription: str  

    @classmethod
    def dataclass_list_from_model(cls, object: list[object]) -> list[PeriodPS3838]:
        return [cls(**obj) for obj in object['periods']]