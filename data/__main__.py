from datetime import date
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from data import inference
from data.nhs_crawler import get_data_sources, get_sheet
from data.parse import parse
from data.population import add_population
from data.types import (
    Group,
    Location,
    Vaccinated,
    ALL_LOCATIONS,
)

OUTPUT_LATEST_DATA = Path("public/latest.csv")
OUTPUT_LINE_DATA = Path("public/line.csv")
OUTPUT_FRESHNESS = Path("public/freshness.txt")


def main():
    st.header("vaxtldr data fetching")

    data_sources = list(get_data_sources())

    st.write("Parsing vaccinated")
    vaccinated_by_source = {
        source: list(parse(source, get_sheet(source))) for source in data_sources
    }
    for source, vaccinated in vaccinated_by_source.items():
        assert len(vaccinated) > 0, f"Data source didn't return any data: {source}"
    vaccinated: List[Vaccinated] = [v for vs in vaccinated_by_source.values() for v in vs]
    # We don't currently use location data, so just get rid of it all.
    vaccinated = [v for v in vaccinated if v.slice.location == ALL_LOCATIONS]

    st.write("Deaggregating")
    vaccinated = inference.add_deaggregates(vaccinated)
    vaccinated = list(inference.remove_aggregates(vaccinated))

    today = date.today()
    latest = max(v.source.real_date for v in vaccinated if not v.extrapolated)
    OUTPUT_FRESHNESS.write_text(today.strftime("%Y-%m-%d") + " " + latest.strftime("%Y-%m-%d"))

    st.write("Adding dose 2 + 2 weeks")
    vaccinated_with_ages = inference.add_dose_2_wait(vaccinated)

    df_with_ages = vaccinated_to_df(vaccinated_with_ages)

    latest_underlying = df_with_ages[~df_with_ages["extrapolated"]]
    latest_date = latest_underlying["real_date"].max()
    latest_over_80 = (
        latest_underlying[latest_underlying["real_date"] == latest_date]
        .groupby(["dose", "group"])
        .sum("vaccinated")
        .reset_index()
    )
    st.write(latest_over_80)
    latest_all_groups = (
        latest_underlying[(latest_underlying["real_date"] == latest_date)]
        .groupby("dose")
        .sum("vaccinated")
        .reset_index()
    )
    latest_all_groups["group"] = "all"
    latest = pd.concat([latest_over_80, latest_all_groups])
    latest = add_population(latest)
    latest = latest.sort_values(by="group", ascending=False)
    latest = latest.sort_values(by="dose", ascending=False)
    latest.to_csv(OUTPUT_LATEST_DATA)
    st.write(latest)

    st.write("Aggregating across ages")
    st.write(vaccinated_to_df(vaccinated))
    vaccinated = inference.aggregate_ages(vaccinated)
    st.write(vaccinated_to_df(vaccinated))
    st.write("Adding extrapolations")
    vaccinated = list(inference.add_extrapolations(vaccinated))
    st.write("Adding dose 2 + 2 weeks")
    vaccinated = inference.add_dose_2_wait(vaccinated)
    df = vaccinated_to_df(vaccinated)

    line = df.groupby(["dose", "real_date", "extrapolated"]).sum().reset_index()
    line["group"] = "all"
    line = add_population(line)
    line["vaccinated"] = line[["vaccinated", "population"]].min(axis=1)
    line = line.sort_values(by="real_date")
    line.to_csv(OUTPUT_LINE_DATA)
    line["perc"] = line["vaccinated"] / line["population"]

    st.write(df)
    st.write(latest)
    st.write(line)
    df["group_and_dose"] = df["group"] + ", " + df["dose"]
    df = df.groupby(["real_date", "group_and_dose"]).sum().reset_index()
    sns.lineplot(data=df, x="real_date", y="vaccinated", hue="group_and_dose")
    plt.xticks(rotation=90)
    st.pyplot()


def vaccinated_to_df(vaccinated: List[Vaccinated]) -> pd.DataFrame:
    df = pd.DataFrame(vaccinated)
    # Move field to top level.
    df["data_date"] = df["source"].apply(lambda s: s["data_date"])
    df["real_date"] = df["source"].apply(lambda s: s["real_date"])
    df["dose"] = df["slice"].apply(lambda s: s["dose"].csv_str())
    df["group"] = df["slice"].apply(lambda s: Group(**s["group"]).csv_str())
    df["location"] = df["slice"].apply(lambda s: Location(**s["location"]).csv_str())
    df = df.drop("source", axis=1)
    df = df.drop("slice", axis=1)
    df["vaccinated"] = df["vaccinated"].astype(int)
    return df


if __name__ == "__main__":
    main()
