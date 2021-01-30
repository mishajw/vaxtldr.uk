import math
import re
import urllib.request
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List

import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
from data.types import Source, Vaccinated, Slice

# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/tablea21principalprojectionukpopulationinagegroups
POPULATION_BY_GROUP = {
    "<80": 64094000,
    ">=80": 3497000,
    "all": 64094000 + 3497000,
}

FIRST_DAILY_DATA = date(2021, 1, 9)
URL = "https://www.england.nhs.uk/statistics/statistical-work-areas/covid-19-vaccinations/"
# TODO: Some of the weekly come under "all". Use this data too.
URL_REGEX = re.compile(
    r"https://www.england.nhs.uk/statistics/wp-content/uploads/sites"
    r"/\d/\d{4}/\d{2}/"
    r"COVID-19-([Dd]aily|weekly|total)-announced-vaccinations-(\d+-[a-zA-Z]+-\d+)(-\d+)?.xlsx"
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
OUTPUT_LINE_DATA = Path("public/line.csv")


def main():
    st.header("vaxxtldr data fetching")

    data_sources = get_data_sources()

    st.write("Parsing vaccinated")
    vaccinated = [v for source in data_sources for v in parse_df(source, get_sheet(source))]
    st.write("Deaggregating")
    vaccinated = add_deaggregates(vaccinated)
    vaccinated = list(remove_aggregates(vaccinated))
    st.write("Extrapolating dose 1 predictions")
    vaccinated = add_extrapolations(vaccinated)
    st.write("Extrapolating 12 week lag")
    vaccinated = add_12w_dose_lag(vaccinated)
    st.write("Adding dose 2 + 2 weeks")
    vaccinated = add_dose_2_wait(vaccinated)

    df = pd.DataFrame(vaccinated)
    # Move field to top level.
    df["data_date"] = df["source"].apply(lambda s: s["data_date"])
    df["real_date"] = df["source"].apply(lambda s: s["real_date"])
    df["dose"] = df["slice"].apply(lambda s: s["dose"])
    df["group"] = df["slice"].apply(lambda s: s["group"])
    df["location"] = df["slice"].apply(lambda s: s["location"])
    df = df.drop("source", axis=1)
    df = df.drop("slice", axis=1)

    latest_underlying = df[~df["extrapolated"]]
    latest_over_80 = (
        latest_underlying[
            (latest_underlying["real_date"] == latest_underlying["real_date"].max())
            & (latest_underlying["group"] == ">=80")
        ]
        .groupby("dose")
        .sum("vaccinated")
        .reset_index()
    )
    latest_all_groups = (
        latest_underlying[(latest_underlying["real_date"] == latest_underlying["real_date"].max())]
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

    line = df.groupby(["dose", "real_date", "extrapolated"]).sum().reset_index()
    line["group"] = "all"
    line = add_population(line)
    line["vaccinated"] = line[["vaccinated", "population"]].min(axis=1)
    line = line.sort_values(by="dose", ascending=False)
    line = line.sort_values(by="real_date")
    line.to_csv(OUTPUT_LINE_DATA)

    st.write(df)
    st.write(latest)
    st.write(line)
    df["group_and_dose"] = df["group"] + ", " + df["dose"]
    df = df.groupby(["real_date", "group_and_dose"]).sum().reset_index()
    sns.lineplot(data=df, x="real_date", y="vaccinated", hue="group_and_dose")
    plt.xticks(rotation=90)
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
        if period == "total":
            period = "weekly"
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
                    deaggregates.extend(deaggregate_with_interpolation(aggregate, dim, vaccinated))
                    continue

                unaggregate_sum = sum(v.vaccinated for v in unaggregates)
                difference = abs(aggregate.vaccinated - unaggregate_sum)
                assert (
                    difference < 1000 or difference / unaggregate_sum < 0.05
                ), f"{aggregate.vaccinated} vs. {unaggregate_sum}"
    return vaccinated + deaggregates


def remove_aggregates(vaccinated: List[Vaccinated]) -> Iterable[Vaccinated]:
    for v in vaccinated:
        if v.slice.group == "all" or v.slice.dose == "all":
            continue
        if v.slice.location != "all":
            # TODO: Verify that we can remove deagg'd location data.
            continue
        if v.source.real_date >= FIRST_DAILY_DATA and v.source.period == "weekly":
            continue
        yield v


def add_extrapolations(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    max_date = max(v.source.real_date for v in vaccinated)

    predictions = []
    for slice in {v.slice for v in vaccinated}:
        array = np.array(
            [
                [(v.source.real_date - max_date).days, v.vaccinated]
                for v in vaccinated
                if v.slice == slice and v.source.real_date > max_date - timedelta(days=7)
            ]
        )
        if len(array) <= 1:
            continue
        m, b = np.polyfit(array[:, 0], array[:, 1], 1)
        for plus_days in range(1, 52 * 7):
            real_date = max_date + timedelta(days=plus_days)
            predictions.append(
                Vaccinated(
                    Source("prediction", data_date=real_date, real_date=real_date, period="daily"),
                    vaccinated=m * plus_days + b,
                    slice=slice,
                    extrapolated=True,
                )
            )
    return vaccinated + predictions


def add_12w_dose_lag(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    dose1s_by_date_slice = {
        (v.source.real_date, v.slice.location, v.slice.group): v.vaccinated
        for v in vaccinated
        if v.slice.dose == "1"
    }

    new_vaccinated = []
    for v in vaccinated:
        if v.slice.dose != "2":
            new_vaccinated.append(v)
            continue
        dose2 = v

        dose1_date = dose2.source.real_date - timedelta(weeks=12)
        key = dose1_date, dose2.slice.location, dose2.slice.group
        if key not in dose1s_by_date_slice:
            new_vaccinated.append(v)
            continue
        dose1 = dose1s_by_date_slice[key]
        new_vaccinated.append(
            replace(dose2, vaccinated=dose2.vaccinated + dose1, extrapolated=True)
        )
    return new_vaccinated


def add_dose_2_wait(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    max_date = max(v.source.real_date for v in vaccinated if not v.extrapolated)
    dose_2_wait = []
    for v in vaccinated:
        if v.slice.dose != "2":
            continue
        wait_date = v.source.real_date + timedelta(weeks=2)
        dose_2_wait.append(
            replace(
                v,
                slice=replace(v.slice, dose="2_wait"),
                source=replace(v.source, real_date=wait_date),
                extrapolated=v.extrapolated or wait_date > max_date,
            )
        )
    return vaccinated + dose_2_wait


def deaggregate_with_interpolation(
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
        print(
            f"Failed to interpolate "
            f"{aggregate.slice} {aggregate.source.real_date} "
            f"with {len(vaccinated_weekly)} samples"
        )
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
            interpolated=True,
        )


def parse_df(source: Source, df: pd.DataFrame) -> Iterable[Vaccinated]:
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
        data = list(filter(lambda d: not math.isnan(d), data))
        if len(data) == 5:
            u80_dose_1, o80_dose_1, u80_dose_2, o80_dose_2, cumulative = data
        elif len(data) == 7:
            # Data includes percentage of >=80s, ignore it.
            u80_dose_1, o80_dose_1, _, u80_dose_2, o80_dose_2, __, cumulative = data
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
