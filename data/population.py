from typing import Dict

import pandas as pd

from data.types import Group, Vaccinated, ALL_LOCATIONS, ALL_AGES


def add_population(df: pd.DataFrame) -> pd.DataFrame:
    population_by_group = __get_population_by_group()
    df["population"] = df["group"].apply(lambda group: population_by_group[group])
    df["vaccinated"] = df[["population", "vaccinated"]].min(axis=1)
    return df


def get_population(vaccinated: Vaccinated) -> int:
    assert vaccinated.slice.location == ALL_LOCATIONS
    return __get_population_by_group()[vaccinated.slice.group]


def total_population() -> int:
    population_by_group = __get_population_by_group()
    return population_by_group[ALL_AGES.csv_str()]


# Source: https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2021/03/COVID-19-weekly-announced-vaccinations-11-March-2021
def __get_population_by_group() -> Dict[Group, int]:
    disjoint_ages = {
        Group(0, 15): 10_816_679,
        Group(16, 44): 20_710_807,
        Group(45, 49): 3_715_812,
        Group(50, 54): 3_907_461,
        Group(55, 59): 3_670_651,
        Group(60, 64): 3_111_835,
        Group(65, 69): 2_796_740,
        Group(70, 74): 2_779_326,
        Group(75, 79): 1_940_686,
        Group(80, None): 2_836_964,
    }

    cumulative_ages = dict()
    cumulative_sum = 0
    for group in sorted(disjoint_ages.keys(), key=lambda g: g.age_lower):
        cumulative_sum += disjoint_ages[group]
        if group.age_lower == 0:
            continue
        cumulative_ages[Group(0, group.age_upper)] = cumulative_sum

    return {k.csv_str(): v for k, v in {**disjoint_ages, **cumulative_ages}.items()}
