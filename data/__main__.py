import math
import re
import urllib.request
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import seaborn as sns
import streamlit as st
from bs4 import BeautifulSoup

# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/tablea21principalprojectionukpopulationinagegroups
POPULATION_BY_GROUP = {
    "<80": 64094000,
    ">=80": 3497000,
    "all": 64094000 + 3497000,
}

FIRST_DATA_DATE = date(2021, 1, 11)
URL = "https://www.england.nhs.uk/statistics/statistical-work-areas/covid-19-vaccinations/"
# TODO: Some of the weekly come under "all". Use this data too.
URL_REGEX = re.compile(
    r"https://www.england.nhs.uk/statistics/wp-content/uploads/sites"
    r"/\d/\d{4}/\d{2}/"
    r"COVID-19-([Dd]aily|weekly)-announced-vaccinations-(\d+-[a-zA-Z]+-\d+)(-\d+)?.xlsx"
)
DATES_WITH_2ND_SHEET = {
    date(2021, 1, 12),
    date(2021, 1, 13),
    date(2021, 1, 14),
    date(2021, 1, 16),
}
SLICE_DIMS = ["dose", "group", "location"]
CACHE_DIR = Path("/tmp/vaxxtldr")
OUTPUT_LATEST_DATA = Path("public/latest.csv")


@dataclass
class Source:
    url: str
    data_date: date
    real_date: date
    period: str


@dataclass
class Slice:
    dose: str
    group: str = "all"
    location: str = "all"


@dataclass
class Vaccinated:
    source: Source
    vaccinated: int
    slice: Slice
    extrapolated: bool = False


def main():
    st.header("vaxxtldr data fetching")

    data_sources = get_data_sources()

    vaccinated = [v for source in data_sources for v in parse_df(source, get_sheet(source))]
    vaccinated = add_deaggregates(vaccinated)
    vaccinated = list(remove_aggregates(vaccinated))

    df = pd.DataFrame(vaccinated)
    # Move field to top level.
    df["data_date"] = df["source"].apply(lambda s: s["data_date"])
    df["real_date"] = df["source"].apply(lambda s: s["real_date"])
    df["dose"] = df["slice"].apply(lambda s: s["dose"])
    df["group"] = df["slice"].apply(lambda s: s["group"])
    df["location"] = df["slice"].apply(lambda s: s["location"])
    df = df.drop("source", axis=1)
    df = df.drop("slice", axis=1)

    latest_over_80 = (
        df[(df["real_date"] == df["real_date"].max()) & (df["group"] == ">=80")]
        .groupby("dose")
        .sum("vaccinated")
        .reset_index()
    )
    latest_all_groups = (
        df[(df["real_date"] == df["real_date"].max())]
            .groupby("dose")
            .sum("vaccinated")
            .reset_index()
    )
    latest_over_80["group"] = ">=80"
    latest_all_groups["group"] = "all"
    latest = pd.concat([latest_over_80, latest_all_groups])
    latest = add_population(latest)
    latest = latest.sort_values(by="group", ascending=False)
    latest = latest.sort_values(by="dose", ascending=False)
    latest.to_csv(OUTPUT_LATEST_DATA)

    st.write(df)
    st.write(latest)
    df = df.groupby(["real_date", "group"]).sum("vaccinated").reset_index()
    sns.lineplot(data=df, x="real_date", y="vaccinated", hue="group")
    st.pyplot()


def get_data_sources() -> Iterable[Source]:
    html = urllib.request.urlopen(URL).read()
    urls = [
        tag["href"]
        for tag in BeautifulSoup(html, "html.parser").find_all()
        if tag.name == "a" and "announced vaccinations" in tag.text
    ]

    for url in urls:
        match = URL_REGEX.match(url)
        if match is None:
            continue
        assert match, url
        period = match.group(1).lower()
        data_date_str = match.group(2)
        data_date = datetime.strptime(data_date_str, "%d-%B-%Y").date()
        delay = timedelta(days=1 if period == "daily" else 4)
        yield Source(url=url, data_date=data_date, real_date=data_date - delay, period=period)


def get_sheet(source: Source) -> pd.DataFrame:
    if not CACHE_DIR.is_dir():
        CACHE_DIR.mkdir(parents=True)
    name = source.url.split("/")[-1]
    cache_file = CACHE_DIR / name
    if not cache_file.is_file():
        sheet_data = urllib.request.urlopen(source.url).read()
        cache_file.write_bytes(sheet_data)
    else:
        sheet_data = cache_file.read_bytes()

    sheet_number = 0
    if source.data_date in DATES_WITH_2ND_SHEET:
        sheet_number = 1
    if source.period == "weekly":
        sheet_number = 1
    return pd.read_excel(sheet_data, sheet_name=sheet_number)


def add_deaggregates(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    deaggregates = []
    vaccinated_daily = [v for v in vaccinated if v.source.period == "daily"]
    for dim in SLICE_DIMS:
        other_dims = [d for d in SLICE_DIMS if d != dim]

        for real_date in {v.source.real_date for v in vaccinated_daily}:
            vaccinated_on_date = [v for v in vaccinated_daily if v.source.real_date == real_date]

            aggregates = [v for v in vaccinated_on_date if getattr(v.slice, dim) == "all"]

            for aggregate in aggregates:
                unaggregates = [
                    v
                    for v in vaccinated_on_date
                    if getattr(v.slice, dim) != "all"
                    and all(
                        getattr(v.slice, other_dim) == getattr(aggregate.slice, other_dim)
                        and getattr(v.slice, other_dim) != "all"
                        for other_dim in other_dims
                    )
                    and v.slice.group == aggregate.slice.group
                    and v.slice.location == aggregate.slice.location
                ]
                if len(unaggregates) == 0:
                    deaggregates.extend(deaggregate_with_extrapolation(aggregate, dim, vaccinated))
                    continue

                unaggregate_sum = sum(v.vaccinated for v in unaggregates)
                difference = abs(aggregate.vaccinated - unaggregate_sum)
                assert (
                    difference < 1000 or difference / unaggregate_sum < 0.05
                ), f"{aggregate.vaccinated} vs. {unaggregate_sum}"
    return vaccinated + deaggregates


def remove_aggregates(vaccinated: List[Vaccinated]) -> Iterable[Vaccinated]:
    for v in vaccinated:
        if any(getattr(v.slice, dim) == "all" for dim in SLICE_DIMS) or v.source.period == "weekly":
            continue
        yield v


def deaggregate_with_extrapolation(
    aggregate: Vaccinated, dim: str, vaccinated: List[Vaccinated]
) -> Iterable[Vaccinated]:
    other_dims = [d for d in SLICE_DIMS if d != dim]

    vaccinated_weekly = [
        v
        for v in vaccinated
        if v.source.period == "weekly"
        if getattr(v.slice, dim) != "all"
        and all(
            getattr(v.slice, other_dim) == getattr(aggregate.slice, other_dim)
            for other_dim in other_dims
        )
    ]

    if len(vaccinated_weekly) < 2:
        print(f"Failed to extrapolate {aggregate.slice} with {len(vaccinated_weekly)} samples")
        yield from []
        return

    dates: List[date] = list(
        sorted(
            {v.source.real_date for v in vaccinated_weekly},
            key=lambda d: abs((d - aggregate.source.real_date).days),
        )
    )
    dates = dates[:2]
    dates = list(sorted(dates))

    dim_date_vaccinated = [
        (getattr(v.slice, dim), v.source.real_date, v.vaccinated)
        for v in vaccinated_weekly
        if v.source.real_date in dates
    ]

    for dim_value in {getattr(v.slice, dim) for v in vaccinated_weekly}:
        ratio0 = sum(
            v for d, ddate, v in dim_date_vaccinated if ddate == dates[0] and d == dim_value
        ) / sum(v for _, ddate, v in dim_date_vaccinated if ddate == dates[0])
        ratio1 = sum(
            v for d, ddate, v in dim_date_vaccinated if ddate == dates[1] and d == dim_value
        ) / sum(v for _, ddate, v in dim_date_vaccinated if ddate == dates[1])

        ratio_delta_per_day = (ratio1 - ratio0) / (dates[1] - dates[0]).days
        ratio = ratio0 + ratio_delta_per_day * (aggregate.source.data_date - dates[0]).days
        yield Vaccinated(
            source=aggregate.source,
            vaccinated=int(aggregate.vaccinated * ratio),
            slice=replace(aggregate.slice, **{dim: dim_value}),
            extrapolated=True,
        )


# def fill_in_groups(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
#     slices = itertools.product(
#         {v.group for v in vaccinated},
#         {v.dose for v in vaccinated},
#         {v.location for v in vaccinated},
#     )
#
#     for group, dose, location in slices:
#         vaccinated_in_slice = [
#             v
#             for v in vaccinated
#             if v.group == group
#             and v.dose == dose
#             and v.location == location
#             and v.source.period == "weekly"
#         ]
#
#         if any(v.source.period == "daily" for v in vaccinated_in_slice):
#             # No filling in needed.
#             continue
#
#         vaccinated_by_date = {v.source.real_date: v.vaccinated for v in vaccinated_in_slice}
#
#         st.write(vaccinated_by_date)
#         dates: List[date] = list(sorted(vaccinated_by_date.keys()))
#         for start, end in zip(dates, dates[1:]):
#             # for days in range((start - end).days):
#
#             st.write(start, end)
#
#     # original = vaccinated
#     # vaccinated = list(filter(lambda v: v.location == "all", vaccinated))
#     # [for v in vaccinated if v.group == "<80"]
#


def parse_df(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
    if source.period == "daily":
        if source.data_date >= date(2021, 1, 18):
            return parse_df_from_2020_01_18(source, df)
        else:
            return parse_df_earliest(source, df)
    elif source.period == "weekly":
        return parse_df_weekly(source, df)
    else:
        raise AssertionError()


def parse_df_from_2020_01_18(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
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


def parse_df_earliest(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
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


def parse_df_weekly(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
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
        u80_dose_1, o80_dose_1, u80_dose_2, o80_dose_2, cumulative = filter(
            lambda d: not math.isnan(d), data
        )
        if location == "Total":
            location = "all"
        yield Vaccinated(source, u80_dose_1, Slice(group="<80", location=location, dose="1"))
        yield Vaccinated(source, o80_dose_1, Slice(group=">=80", location=location, dose="1"))
        yield Vaccinated(source, u80_dose_2, Slice(group="<80", location=location, dose="2"))
        yield Vaccinated(source, o80_dose_2, Slice(group=">=80", location=location, dose="2"))
        yield Vaccinated(source, cumulative, Slice(location=location, dose="all"))


def add_population(df: pd.DataFrame) -> pd.DataFrame:
    df["population"] = df["group"].apply(lambda group: POPULATION_BY_GROUP[group])
    return df


if __name__ == "__main__":
    main()
