from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from data import inference
from data.nhs_crawler import get_data_sources, get_sheet
from data.parse import parse
from data.population import add_population

OUTPUT_LATEST_DATA = Path("public/latest.csv")
OUTPUT_LINE_DATA = Path("public/line.csv")
OUTPUT_FRESHNESS = Path("public/freshness.txt")


def main():
    st.header("vaxtldr data fetching")

    data_sources = get_data_sources()

    st.write("Parsing vaccinated")
    vaccinated_by_source = {source: list(parse(source, get_sheet(source))) for source in data_sources}
    for source, vaccinated in vaccinated_by_source.items():
        assert len(vaccinated) > 0, f"Data source didn't return any data: {source}"
    vaccinated = [v for vs in vaccinated_by_source.values() for v in vs]
    st.write("Deaggregating")
    vaccinated = inference.add_deaggregates(vaccinated)
    vaccinated = list(inference.remove_aggregates(vaccinated))
    st.write("Extrapolating dose 1 predictions")
    vaccinated = inference.add_extrapolations(vaccinated)
    st.write("Decumulating")
    vaccinated = list(inference.make_non_cumulative(vaccinated))
    st.write("Extrapolating 12 week lag")
    vaccinated = inference.add_12w_dose_lag(vaccinated)
    st.write("Cumulating")
    vaccinated = list(inference.make_cumulative(vaccinated))
    st.write("Adding dose 2 + 2 weeks")
    vaccinated = inference.add_dose_2_wait(vaccinated)

    df = pd.DataFrame(vaccinated)
    # Move field to top level.
    df["data_date"] = df["source"].apply(lambda s: s["data_date"])
    df["real_date"] = df["source"].apply(lambda s: s["real_date"])
    df["dose"] = df["slice"].apply(lambda s: s["dose"])
    df["group"] = df["slice"].apply(lambda s: s["group"])
    df["location"] = df["slice"].apply(lambda s: s["location"])
    df = df.drop("source", axis=1)
    df = df.drop("slice", axis=1)
    df["vaccinated"] = df["vaccinated"].astype(int)

    latest_underlying = df[~df["extrapolated"]]
    latest_date = latest_underlying["real_date"].max()
    latest_over_80 = (
        latest_underlying[
            (latest_underlying["real_date"] == latest_date) & (latest_underlying["group"] == ">=80")
        ]
        .groupby("dose")
        .sum("vaccinated")
        .reset_index()
    )
    latest_all_groups = (
        latest_underlying[(latest_underlying["real_date"] == latest_date)]
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

    today = date.today()
    latest = max(v.source.real_date for v in vaccinated if not v.extrapolated)
    OUTPUT_FRESHNESS.write_text(today.strftime("%Y-%m-%d") + " " + latest.strftime("%Y-%m-%d"))

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


if __name__ == "__main__":
    main()
