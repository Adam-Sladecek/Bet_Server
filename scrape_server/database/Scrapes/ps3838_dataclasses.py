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