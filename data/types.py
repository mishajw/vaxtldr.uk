from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class Source:
    url: str
    data_date: date
    real_date: date
    period: str


class Dose(Enum):
    ALL = 0
    DOSE_1 = 1
    DOSE_2 = 2
    DOSE_2_PLUS_WAIT = 3

    def is_all(self) -> bool:
        return self == Dose.ALL

    def csv_str(self) -> str:
        if self == Dose.DOSE_1:
            return "1"
        elif self == Dose.DOSE_2:
            return "2"
        elif self == Dose.DOSE_2_PLUS_WAIT:
            return "2_wait"
        elif self == Dose.ALL:
            return "all"


@dataclass(frozen=True)
class Group:
    age_lower: int
    age_upper: Optional[int]

    def is_all(self) -> bool:
        return self == ALL_AGES

    def csv_str(self) -> str:
        if self == UNDER_80S:
            return "<80"
        elif self == OVER_80S:
            return ">=80"
        raise AssertionError()


@dataclass(frozen=True)
class Location:
    name: Optional[str]

    def is_all(self) -> bool:
        return self.name is None

    def csv_str(self) -> str:
        return self.name if self.name is None else "all"


ALL_AGES = Group(0, None)
UNDER_80S = Group(0, 79)
OVER_80S = Group(80, None)
ALL_LOCATIONS = Location(None)


@dataclass(frozen=True)
class Slice:
    dose: Dose
    group: Group = ALL_AGES
    location: Location = ALL_LOCATIONS


@dataclass
class Vaccinated:
    source: Source
    vaccinated: int
    slice: Slice
    interpolated: bool = False
    extrapolated: bool = False
