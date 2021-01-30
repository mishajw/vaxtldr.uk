from dataclasses import dataclass
from datetime import date


@dataclass
class Source:
    url: str
    data_date: date
    real_date: date
    period: str


@dataclass(frozen=True)
class Slice:
    dose: str
    group: str = "all"
    location: str = "all"


@dataclass
class Vaccinated:
    source: Source
    vaccinated: int
    slice: Slice
    interpolated: bool = False
    extrapolated: bool = False
