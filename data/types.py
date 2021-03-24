import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


AGE_LT = re.compile(r"Under (\d+)")
AGE_BETWEEN = re.compile(r"(\d+)-(\d+)")
AGE_GTE = re.compile(r"(\d+)\+")


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


# TODO: Rename to ages.
@dataclass(frozen=True)
class Group:
    age_lower: int
    age_upper: Optional[int]

    def is_all(self) -> bool:
        return self == ALL_AGES

    def csv_str(self) -> str:
        if self.age_lower == 0 and self.age_upper is None:
            return "all"
        elif self.age_lower == 0:
            return f"<={self.age_upper}"
        elif self.age_upper is not None:
            return f"{self.age_lower}-{self.age_upper}"
        else:
            return f">={self.age_lower}"

    def overlaps(self, other: "Group") -> bool:
        self_upper = self.age_upper if self.age_upper is not None else 10000
        other_upper = other.age_upper if other.age_upper is not None else 10000
        return self.age_lower <= other_upper and self_upper >= other.age_lower

    @staticmethod
    def from_csv_str(s: str) -> "Group":
        age_lt = AGE_LT.match(s)
        if age_lt is not None:
            return Group(0, int(age_lt.group(1)) - 1)
        age_between = AGE_BETWEEN.match(s)
        if age_between is not None:
            return Group(int(age_between.group(1)), int(age_between.group(2)))
        age_gte = AGE_GTE.match(s)
        if age_gte is not None:
            return Group(int(age_gte.group(1)), None)
        raise AssertionError(f"Could not parse {s} as Group")


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
ALL_DOSES = Dose.ALL


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
