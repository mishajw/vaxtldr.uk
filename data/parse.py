import math
from datetime import date
from typing import Iterable

import pandas as pd
from data.types import Source, Vaccinated, Slice


def parse(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
    # Data overrides. Some data formats are only used once, and not worth writing parsers for.
    if source.data_date == date(2021, 1, 7) and source.period == "weekly":
        return [
            Vaccinated(source, 438075, Slice("1", "<80", "all")),
            Vaccinated(source, 13567, Slice("2", "<80", "all")),
            Vaccinated(source, 654810, Slice("1", ">=80", "all")),
            Vaccinated(source, 6414, Slice("2", ">=80", "all")),
        ]
    elif source.data_date == date(2020, 12, 31) and source.period == "weekly":
        return [
            Vaccinated(source, 261561, Slice("1", "<80", "all")),
            Vaccinated(source, 0, Slice("2", "<80", "all")),
            Vaccinated(source, 524439, Slice("1", ">=80", "all")),
            Vaccinated(source, 0, Slice("2", ">=80", "all")),
        ]

    if source.period == "daily":
        if source.data_date >= date(2021, 1, 18):
            return __parse_df_from_2021_01_18(source, df)
        else:
            return __parse_df_earliest(source, df)
    elif source.period == "weekly":
        return __parse_df_weekly(source, df)
    else:
        raise AssertionError()


def __parse_df_from_2021_01_18(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
    df = df.drop("Unnamed: 0", axis=1)
    df_iterrows = df.iterrows()

    for row in df_iterrows:
        _, (title, *data) = row
        if type(title) == str and title.lower() == "region of residence":
            break

    for row in df_iterrows:
        _, (location, *data) = row
        if type(location) == float and math.isnan(location):
            continue
        if location == "Data quality notes:":
            break
        dose_1, dose_2, cumulative = filter(lambda d: not math.isnan(d), data)
        if location == "Total":
            location = "all"
        yield Vaccinated(source, dose_1, Slice(location=location, dose="1"))
        yield Vaccinated(source, dose_2, Slice(location=location, dose="2"))
        yield Vaccinated(source, cumulative, Slice(location=location, dose="all"))


def __parse_df_earliest(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
    df = df.drop("Unnamed: 0", axis=1)
    for row in df.iterrows():
        _, (title, *data) = row
        if type(title) == str and " to " in title and len(title.split()) == 7:
            dose = "all"
        elif type(title) == str and title.strip().lower() == "of which, 1st dose":
            dose = "1"
        elif type(title) == str and title.strip().lower() == "of which, 2nd dose":
            dose = "2"
        else:
            continue
        vaccinated = data[1]
        yield Vaccinated(source, vaccinated, Slice(dose=dose))


def __parse_df_weekly(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
    df = df.drop("Unnamed: 0", axis=1)
    df_iterrows = df.iterrows()

    for row in df_iterrows:
        _, (title, *data) = row
        if type(title) == str and title.lower() == "region of residence":
            break

    for row in df_iterrows:
        _, (location, *data) = row
        if type(location) == float and math.isnan(location):
            continue
        if location == "Data quality notes:":
            break
        data = list(filter(lambda d: not math.isnan(d), data))
        if len(data) == 5:
            u80_dose_1, o80_dose_1, u80_dose_2, o80_dose_2, cumulative = data
        elif len(data) == 7:
            # Data includes percentage of >=80s, ignore it.
            u80_dose_1, o80_dose_1, _, u80_dose_2, o80_dose_2, __, cumulative = data
        elif len(data) == 7 * 2 + 1:
            u80_dose_1 = sum(data[0:3])
            o80_dose_1 = data[3]
            u80_dose_2 = sum(data[7 : 7 + 3])
            o80_dose_2 = data[7 + 3]
            cumulative = data[7 + 7]
        else:
            raise AssertionError(source, data)
        if location == "Total":
            location = "all"
        yield Vaccinated(source, u80_dose_1, Slice(group="<80", location=location, dose="1"))
        yield Vaccinated(source, o80_dose_1, Slice(group=">=80", location=location, dose="1"))
        yield Vaccinated(source, u80_dose_2, Slice(group="<80", location=location, dose="2"))
        yield Vaccinated(source, o80_dose_2, Slice(group=">=80", location=location, dose="2"))
        yield Vaccinated(source, cumulative, Slice(location=location, dose="all"))
